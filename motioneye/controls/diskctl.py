# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

import logging
import os
import re
import sys

from motioneye import utils


def _read_mount_table() -> str:
    """Returns the mounted file systems, one per line, starting with the target,
    mount point, file system type and options. Linux has them in /proc/mounts,
    FreeBSD has no /proc/mounts but prints them the same way with "mount -p"."""
    try:
        with open('/proc/mounts') as f:
            return f.read()

    except FileNotFoundError:
        return utils.call_subprocess(['mount', '-p'])


def _list_mounts():
    logging.debug('listing mounts...')

    seen_targets = set()

    mounts = []
    for line in _read_mount_table().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue

        target = parts[0]
        mount_point = parts[1]
        fstype = parts[2]
        opts = parts[3]

        if target in seen_targets:
            continue  # probably a bind mount

        seen_targets.add(target)

        if fstype == 'fuseblk':
            fstype = 'ntfs'  # most likely

        logging.debug(f'found mount "{target}" at "{mount_point}"')

        mounts.append(
            {
                'target': target,
                'mount_point': mount_point,
                'fstype': fstype,
                'opts': opts,
                # Used by the UI to mark unwritable mounts.
                'writable': os.access(mount_point, os.W_OK),
            }
        )

    return mounts


def _list_disks():
    if os.path.exists('/dev/disk/by-id/'):
        return _list_disks_dev_by_id()

    elif sys.platform.startswith('freebsd'):
        return _list_disks_geom()

    else:  # fall back to fdisk -l
        return _list_disks_fdisk()


def _parse_geom_list(output: str) -> list[dict]:
    # "geom disk list" and "geom part list" print a block per geom, starting with
    # "Geom name: ...", which lists its providers as "1. Name: ...", each followed
    # by "key: value" lines
    geoms: list[dict] = []
    provider: dict[str, str] | None = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith('Geom name: '):
            geoms.append({'name': line[11:], 'providers': []})
            provider = None

        elif line == 'Providers:':
            provider = {}

        elif line == 'Consumers:':
            provider = None

        elif provider is not None and geoms:
            m = re.match(r'(?:\d+\. )?(\w+): ?(.*)$', line)
            if not m:
                continue

            key, value = m.groups()
            if key == 'Name':
                provider = {}
                geoms[-1]['providers'].append(provider)

            provider[key.lower()] = value

    return geoms


def _list_disks_geom():
    logging.debug('listing disks using geom')

    try:
        disk_output = utils.call_subprocess(['geom', 'disk', 'list'])
        part_output = utils.call_subprocess(['geom', 'part', 'list'])

    except Exception:
        logging.exception('failed to list disks using geom')
        return []

    disks_by_name = {}
    for geom in _parse_geom_list(disk_output):
        for provider in geom['providers']:
            if provider.get('mediasize', '').startswith('0 '):
                continue  # e.g. an empty optical drive

            # FreeBSD 14 prints "(null)" for a disk without description
            descr = provider.get('descr', '')
            disks_by_name[provider['name']] = {
                'target': '/dev/' + provider['name'],
                'bus': '',
                'vendor': '' if descr == '(null)' else descr,
                'model': '',
                'partitions': [],
            }

    for geom in _parse_geom_list(part_output):
        disk = disks_by_name.get(geom['name'])
        if not disk:  # e.g. a memory disk, which is no disk geom
            disk = disks_by_name[geom['name']] = {
                'target': '/dev/' + geom['name'],
                'bus': '',
                'vendor': '',
                'model': '',
                'partitions': [],
            }

        for provider in geom['providers']:
            disk['partitions'].append(
                {
                    'target': '/dev/' + provider['name'],
                    'bus': '',
                    'vendor': disk['vendor'],
                    'model': disk['model'],
                    'part_no': int(provider.get('index', 0)),
                }
            )

    disks = []
    for disk in disks_by_name.values():
        if not disk['partitions']:  # a file system on the whole disk
            partition = {k: v for k, v in disk.items() if k != 'partitions'}
            disk['partitions'].append(dict(partition, part_no=1))

        logging.debug(
            f'found disk at "{disk["target"]}": "{disk["vendor"]}" with '
            f'partitions {[p["target"] for p in disk["partitions"]]}'
        )
        disks.append(disk)

    disks.sort(key=lambda d: d['target'])

    for disk in disks:
        disk['partitions'].sort(key=lambda p: p['part_no'])

    return disks


def _list_geom_labels() -> dict[str, str]:
    # FreeBSD mounts partitions by their labels as well, like /dev/gpt/cams or
    # /dev/msdosfs/CAMS for /dev/da0p1
    try:
        output = utils.call_subprocess(['glabel', 'status', '-s'])

    except Exception:
        logging.exception('failed to list labels using glabel')
        return {}

    labels = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 3:
            labels['/dev/' + parts[0]] = '/dev/' + parts[2]

    return labels


def _list_mounts_by_target():
    mounts_by_target = {m['target']: m for m in _list_mounts()}
    if sys.platform.startswith('freebsd'):
        for label, target in _list_geom_labels().items():
            if label in mounts_by_target and target not in mounts_by_target:
                mounts_by_target[target] = dict(mounts_by_target[label], target=target)

    return mounts_by_target


def _list_disks_dev_by_id():
    logging.debug('listing disks using /dev/disk/by-id/')

    disks_by_dev = {}
    partitions_by_dev = {}

    for entry in os.listdir('/dev/disk/by-id/'):
        parts = entry.split('-', 1)
        if len(parts) < 2:
            continue

        target = os.path.realpath(os.path.join('/dev/disk/by-id/', entry))

        bus, entry = parts
        m = re.search(r'-part(\d+)$', entry)
        if m:
            part_no = int(m.group(1))
            entry = re.sub(r'-part\d+$', '', entry)

        else:
            part_no = None

        parts = entry.split('_')
        if len(parts) < 2:
            vendor = parts[0]
            model = ''

        else:
            vendor, model = parts[:2]

        if part_no is not None:
            logging.debug(
                f'found partition "{part_no}" at "{target}" on bus "{bus}": "{vendor} {model}"'
            )

            partitions_by_dev[target] = {
                'target': target,
                'bus': bus,
                'vendor': vendor,
                'model': model,
                'part_no': part_no,
                'unmatched': True,
            }

        else:
            logging.debug(
                f'found disk at "{target}" on bus "{bus}": "{vendor} {model}"'
            )

            disks_by_dev[target] = {
                'target': target,
                'bus': bus,
                'vendor': vendor,
                'model': model,
                'partitions': [],
            }

    # group partitions by disk
    for dev, partition in list(partitions_by_dev.items()):
        for disk_dev, disk in list(disks_by_dev.items()):
            if dev.startswith(disk_dev):
                disk['partitions'].append(partition)
                partition.pop('unmatched', None)

    # add separate partitions that did not match any disk
    for partition in list(partitions_by_dev.values()):
        if partition.pop('unmatched', False):
            disks_by_dev[partition['target']] = partition
            partition['partitions'] = [dict(partition)]

    # prepare flat list of disks
    disks = list(disks_by_dev.values())
    disks.sort(key=lambda d: d['vendor'])

    for disk in disks:
        disk['partitions'].sort(key=lambda p: p['part_no'])

    return disks


def _list_disks_fdisk():
    try:
        output = utils.call_subprocess(['fdisk', '-l'])

    except Exception:
        logging.exception('failed to list disks using "fdisk -l"')
        return []

    disks = []
    disk = None

    def add_disk(d):
        logging.debug(
            f'found disk at "{d["target"]}" on bus "{d["bus"]}": "{d["vendor"]} {d["model"]}"'
        )

        for part in d['partitions']:
            logging.debug(
                f'found partition "{part["part_no"]}" at "{part["target"]}" '
                f'on bus "{part["bus"]}": "{part["vendor"]} {part["model"]}"'
            )

        disks.append(d)

    for line in output.split('\n'):
        line = line.replace('*', '')
        line = re.sub(r'\s+', ' ', line.strip())
        if not line:
            continue

        if line.startswith('Disk /dev/'):
            if disk and disk['partitions']:
                add_disk(disk)

            parts = line.split()

            disk = {
                'target': parts[1].strip(':'),
                'bus': '',
                'vendor': '',
                'model': parts[2] + ' ' + parts[3].strip(','),
                'partitions': [],
            }

        elif line.startswith('/dev/') and disk:
            parts = line.split()
            part_no = re.findall(r'\d+$', parts[0])
            partition = {
                'part_no': int(part_no[0]) if part_no else None,
                'target': parts[0],
                'bus': '',
                'vendor': '',
                'model': parts[4] + ' ' + ' '.join(parts[6:]),
            }

            disk['partitions'].append(partition)

    if disk and disk['partitions']:
        add_disk(disk)

    disks.sort(key=lambda d: d['target'])

    for disk in disks:
        disk['partitions'].sort(key=lambda p: p['part_no'])

    return disks


def list_mounted_disks():
    mounted_disks = []

    try:
        disks = _list_disks()
        mounts_by_target = _list_mounts_by_target()

        for disk in disks:
            for partition in disk['partitions']:
                mount = mounts_by_target.get(partition['target'])
                if mount:
                    partition.update(mount)

            # filter out unmounted partitions
            disk['partitions'] = [p for p in disk['partitions'] if p.get('mount_point')]

        # filter out unmounted disks
        mounted_disks = [d for d in disks if d['partitions']]

    except Exception:
        logging.exception('failed to list mounted disks')

    return mounted_disks


def list_mounted_partitions():
    mounted_partitions = {}

    try:
        disks = _list_disks()
        mounts_by_target = _list_mounts_by_target()

        for disk in disks:
            for partition in disk['partitions']:
                mount = mounts_by_target.get(partition['target'])
                if mount:
                    partition.update(mount)
                    mounted_partitions[partition['target']] = partition

    except Exception:
        logging.exception('failed to list mounted partitions')

    return mounted_partitions

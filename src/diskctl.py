
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

import logging
import os
import re


def _list_mounts():
    logging.debug('listing mounts...')
    
    mounts = []
    with open('/proc/mounts', 'r') as f:
        for line in f:
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

            if fstype == 'fuseblk':
                fstype = 'ntfs' # most likely'

            logging.debug('found mount "%s" at "%s"' % (target, mount_point))
            
            mounts.append({
                'target': target,
                'mount_point': mount_point,
                'fstype': fstype,
                'opts': opts,
            })

    return mounts


def _list_disks():
    logging.debug('listing disks...')
    
    disks_by_dev = {}
    partitions_by_dev = {}

    for entry in os.listdir('/dev/disk/by-id/'):
        parts = entry.split('-', 1)
        if len(parts) < 2:
            continue
        
        target = os.path.realpath(os.path.join('/dev/disk/by-id/', entry))
        
        bus, entry = parts
        m = re.search('-part(\d+)$', entry)
        if m:
            part_no = int(m.group(1))
            entry = re.sub('-part\d+$', '', entry)
        
        else:
            part_no = None

        parts = entry.split('_')
        if len(parts) < 2:
            vendor = parts[0]
            model = ''
        
        else:
            vendor, model = parts[:2]

        if part_no is not None:
            logging.debug('found partition "%s" at "%s" on bus "%s": "%s %s"' % (part_no, target, bus, vendor, model))
        
            partitions_by_dev[target] = {
                'target': target,
                'bus': bus,
                'vendor': vendor,
                'model': model,
                'part_no': part_no,
                'unmatched': True
            }
            
        else:
            logging.debug('found disk at "%s" on bus "%s": "%s %s"' % (target, bus, vendor, model))

            disks_by_dev[target] = {
                'target': target,
                'bus': bus,
                'vendor': vendor,
                'model': model,
                'partitions': []
            }
        
    # group partitions by disk
    for dev, partition in partitions_by_dev.items():
        for disk_dev, disk in disks_by_dev.items():
            if dev.startswith(disk_dev):
                disk['partitions'].append(partition)
                partition.pop('unmatched')
            
    # add separate partitions that did not match any disk
    for partition in partitions_by_dev.values():
        if partition.pop('unmatched', False):
            disks_by_dev[partition['target']] = partition
            partition['partitions'] = [dict(partition)]

    # prepare flat list of disks
    disks = disks_by_dev.values()
    disks.sort(key=lambda d: d['vendor'])
    
    for disk in disks:
        disk['partitions'].sort(key=lambda p: p['part_no'])

    return disks


def list_mounted_disks():
    mounted_disks = []
    
    try:
        disks = _list_disks()
        mounts_by_target = dict((m['target'], m) for m in _list_mounts())
        
        for disk in disks:
            for partition in disk['partitions']:
                mount = mounts_by_target.get(partition['target'])
                if mount:
                    partition.update(mount) 
        
            # filter out unmounted partitions
            disk['partitions'] = [p for p in disk['partitions'] if p.get('mount_point')]
        
        # filter out unmounted disks
        mounted_disks = [d for d in disks if d['partitions']]

    except Exception as e:
        logging.error('failed to list mounted disks: %s' % e, exc_info=True)
        
    return mounted_disks

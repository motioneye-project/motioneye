# Copyright (c) 2020 Vlsarro
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

import datetime
from typing import Union

__all__ = ('pretty_date_time', 'pretty_date', 'pretty_duration', 'pretty_time')


def pretty_date_time(date_time, tzinfo=None, short=False):
    if date_time is None:
        return '(' + _('never') + ')'

    if isinstance(date_time, int):
        return pretty_date_time(datetime.datetime.fromtimestamp(date_time))

    if short:
        text = '{day} {month}, {hm}'.format(
            day=date_time.day,
            month=date_time.strftime('%b'),
            hm=date_time.strftime('%H:%M'),
        )

    else:
        text = '{day} {month} {year}, {hm}'.format(
            day=date_time.day,
            month=date_time.strftime('%B'),
            year=date_time.year,
            hm=date_time.strftime('%H:%M'),
        )

    if tzinfo:
        offset = tzinfo.utcoffset(datetime.datetime.utcnow()).seconds
        tz = 'GMT'
        if offset >= 0:
            tz += '+'

        else:
            tz += '-'
            offset = -offset

        tz += '%.2d' % (offset // 3600) + ':%.2d' % ((offset % 3600) // 60)

        text += ' (' + tz + ')'

    return text


def pretty_date(d: Union[datetime.date, int]) -> str:
    if d is None:
        return '(' + _('never') + ')'

    if isinstance(d, int):
        return pretty_date(datetime.datetime.fromtimestamp(d))

    return '{day} {month} {year}'.format(
        day=d.day, month=_(d.strftime('%B')), year=d.year
    )


def pretty_time(t: Union[datetime.time, datetime.timedelta]) -> str:
    if t is None:
        return ''

    if isinstance(t, datetime.timedelta):
        hour = t.seconds // 3600
        minute = (t.seconds % 3600) // 60
        t = datetime.time(hour=hour, minute=minute)

    return '{hm}'.format(hm=t.strftime('%H:%M'))


def pretty_duration(duration):
    if duration is None:
        duration = 0

    if isinstance(duration, datetime.timedelta):
        duration = duration.seconds + duration.days * 86400

    if duration < 0:
        negative = True
        duration = -duration

    else:
        negative = False

    days = duration // 86400
    duration %= 86400
    hours = duration // 3600
    duration %= 3600
    minutes = duration // 60
    duration %= 60
    seconds = duration

    # treat special cases
    special_result = None
    if days != 0 and hours == 0 and minutes == 0 and seconds == 0:
        if days == 1:
            special_result = str(days) + ' ' + _('day')

        elif days == 7:
            special_result = '1 ' + _('week')

        elif days in [30, 31, 32]:
            special_result = '1 ' + _('month')

        elif days in [365, 366]:
            special_result = '1 ' + _('year')

        else:
            special_result = str(days) + ' ' + _('days')

    elif days == 0 and hours != 0 and minutes == 0 and seconds == 0:
        if hours == 1:
            special_result = str(hours) + ' ' + _('hour')

        else:
            special_result = str(hours) + ' ' + _('hours')

    elif days == 0 and hours == 0 and minutes != 0 and seconds == 0:
        if minutes == 1:
            special_result = str(minutes) + ' ' + _('minute')

        else:
            special_result = str(minutes) + ' ' + _('minutes')

    elif days == 0 and hours == 0 and minutes == 0 and seconds != 0:
        if seconds == 1:
            special_result = str(seconds) + ' ' + _('second')

        else:
            special_result = str(seconds) + ' ' + _('seconds')

    elif days == 0 and hours == 0 and minutes == 0 and seconds == 0:
        special_result = str(0) + ' ' + _('seconds')

    if special_result:
        if negative:
            special_result = _('minus') + ' ' + special_result

        return special_result

    if days:
        fmt = "{d}d{h}h{m}m"

    elif hours:
        fmt = "{h}h{m}m"

    elif minutes:
        fmt = "{m}m"
        if seconds:
            fmt += "{s}s"

    else:
        fmt = "{s}s"

    if negative:
        fmt = '-' + fmt

    return fmt.format(d=days, h=hours, m=minutes, s=seconds)

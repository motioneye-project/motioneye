
import datetime


def pretty_date_time(date_time, tzinfo=None):
    if date_time is None:
        return '('+  _('never') + ')'

    if isinstance(date_time, int):
        return pretty_date_time(datetime.datetime.fromtimestamp(date_time))

    text = u'{day} {month} {year}, {hm}'.format(
        day=date_time.day,
        month=_(date_time.strftime('%B')),
        year=date_time.year,
        hm=date_time.strftime('%H:%M')
    )
    
    if tzinfo:
        offset = tzinfo.utcoffset(datetime.datetime.utcnow()).seconds
        tz = 'GMT'
        if offset >= 0:
            tz += '+'

        else:
            tz += '-'
            offset = -offset

        tz += '%.2d' % (offset / 3600) + ':%.2d' % ((offset % 3600) / 60)

        text += ' (' + tz + ')'

    return text


def pretty_date(date):
    if date is None:
        return '('+  _('never') + ')'

    if isinstance(date, int):
        return pretty_date(datetime.datetime.fromtimestamp(date))

    return u'{day} {month} {year}'.format(
        day=date.day,
        month=_(date.strftime('%B')),
        year=date.year
    )


def pretty_time(time):
    if time is None:
        return ''

    if isinstance(time, datetime.timedelta):
        hour = time.seconds / 3600
        minute = (time.seconds % 3600) / 60
        time = datetime.time(hour, minute)

    return '{hm}'.format(
        hm=time.strftime('%H:%M')
    )


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

    days = int(duration / 86400)
    duration %= 86400
    hours = int(duration / 3600)
    duration %= 3600
    minutes = int(duration / 60)
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
        format = "{d}d{h}h{m}m"

    elif hours:
        format = "{h}h{m}m"

    elif minutes:
        format = "{m}m"
        if seconds:
            format += "{s}s"

    else:
        format = "{s}s"

    if negative:
        format = '-' + format

    return format.format(d=days, h=hours, m=minutes, s=seconds)

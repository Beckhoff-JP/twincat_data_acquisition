from datetime import datetime

class TwinCATTime:
    EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as MS file time
    DC_BASETIME = datetime(year=2000,month=1,day=1,hour=0,minute=0,second=0)
    EPOCH_AS_DCTIME = 0 - (int(time.mktime(DC_BASETIME.timetuple()) * 1000) + int(DC_BASETIME.microsecond / 1000))  * 10000000 # January 1, 1970 as DC time(ns)
    HUNDREDS_OF_NANOSECONDS = 10000000
    NANOSECONDS = 1000000000


    @classmethod
    def get_dc_time_h32(cls) -> int:
        now = datetime.now()
        ns_now = (int(time.mktime(now.timetuple()) * 1000) + int(now.microsecond / 1000))  * 10000000
        dctime_now = ns_now - cls.EPOCH_AS_DCTIME
        h_32bit = dctime_now & 0xffffffff00000000
        return h_32bit



    @classmethod
    def filetime_to_dt(cls, ft):
        """Converts a Microsoft filetime number to a Python datetime. The new datetime object is time zone-naive but is equivalent to tzinfo=utc.

        >>> filetime_to_dt(116444736000000000)
        datetime.datetime(1970, 1, 1, 0, 0)
        """
        # Get seconds and remainder in terms of Unix epoch
        (s, ns100) = divmod(ft - cls.EPOCH_AS_FILETIME, cls.HUNDREDS_OF_NANOSECONDS)
        # Convert to datetime object
        dt = datetime.fromtimestamp(s)
        # Add remainder in as microseconds. Python 3.2 requires an integer
        dt = dt.replace(microsecond=(ns100 // 10))
        return dt

    @classmethod
    def dctime_to_dt(cls, ft):
        # Get seconds and remainder in terms of Unix epoch
        (s, ns) = divmod(ft - cls.EPOCH_AS_DCTIME, cls.NANOSECONDS)
        # Convert to datetime object
        dt = datetime.fromtimestamp(s)
        # Add remainder in as microseconds. Python 3.2 requires an integer
        dt = dt.replace(microsecond=(ns // 1000))
        return dt
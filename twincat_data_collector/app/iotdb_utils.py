import numpy as np
from iotdb.Session import Session
from iotdb.SessionPool import PoolConfig, SessionPool
from iotdb.utils.IoTDBConstants import TSDataType, TSEncoding, Compressor
from iotdb.utils.NumpyTablet import ColumnType, NumpyTablet
from iotdb.utils.exception import StatementExecutionException, IoTDBConnectionException
from error_handler import IoTDBConnectionError
from dataclasses import dataclass, field
from typing import Tuple, Union, TypeVar
from abc import ABC, abstractmethod
from enum import Enum
from collections import deque
import time
import pyads

class ctsDataType(Enum):
    c_bool = TSDataType.BOOLEAN
    c_byte = TSDataType.INT32
    c_short = TSDataType.INT32
    c_int = TSDataType.INT32
    c_long = TSDataType.INT64
    c_longlong = TSDataType.INT64
    c_ubyte = TSDataType.INT32
    c_ushort = TSDataType.INT32
    c_uint = TSDataType.INT64
    c_ulong = TSDataType.BLOB
    c_ulonglong = TSDataType.BLOB
    c_double = TSDataType.DOUBLE
    c_float = TSDataType.FLOAT
    c_char = TSDataType.TEXT


@dataclass
class IoTDBClientSession:
    host: str = '127.0.0.1'
    port: int = 6667
    username: str = 'root'
    password: str = 'root'
    session_pool : SessionPool = field(default=None)

    def __post_init__(self):
        # 夏時間が有効かどうかのフラグ
        is_dst = time.daylight
        # 時差を計算（秒）
        offset = -time.altzone if is_dst else -time.timezone
        offset = int(offset / 3600)
        pool_config = PoolConfig(
            host=self.host,
            port=self.port,
            user_name=self.username,
            password=self.password,
            fetch_size=1024,
            time_zone=f"UTC{offset:+d}",
            enable_redirection=True
        )
        self.session_pool = SessionPool(pool_config, max_pool_size=5, wait_timeout_in_ms=3000)
        
    def close(self):
        if self.session is not None:
            self.session.close()
            self.session = None


T = TypeVar('T', bound=Union[Tuple[Tuple], pyads.PLCTYPE_BOOL, pyads.PLCTYPE_BYTE, pyads.PLCTYPE_DWORD, pyads.PLCTYPE_INT, pyads.PLCTYPE_DINT, pyads.PLCTYPE_LINT, pyads.PLCTYPE_UDINT, pyads.PLCTYPE_ULINT, pyads.PLCTYPE_REAL, pyads.PLCTYPE_LREAL, pyads.PLCTYPE_STRING, pyads.PLCTYPE_WSTRING])

class SessionManagement:
    @classmethod
    def session(cls, func):
        def wrapper(self, *args, **kwargs):
            try:
                session = self.session_manager.session_pool.get_session()
                func(self,  session, *args, **kwargs)
                self.session_manager.session_pool.put_back(session)
            except IoTDBConnectionException as e:
                print(f"Connection failed for {self.session_manager.host}:{self.session_manager.port}: {e}")
                raise IoTDBConnectionError("Failed to connect to IoTDB") from e
        return wrapper


@dataclass
class IoTTimeSeriesBase(ABC,SessionManagement):
    session_manager : IoTDBClientSession
    plc_data_model : T
    storage_group_name : str
    time_series_name : str
    chunk_size : int = field(default=5)
    queue : deque = field(default_factory=deque)
    
    def __post_init__(self):
        self.mesurements_list = list()

    
    @SessionManagement.session
    def create_storage_group(self, session : Session):
        try:
            session.set_storage_group(self.storage_group_name)
        except StatementExecutionException as e:
            pass
        except IoTDBConnectionException as e:
            raise IoTDBConnectionError(f"Connection fail {self.session_manager.host}, {self.session_manager.port}") from e


    def write_data(self, data) -> bool:
        self.queue.append(data)
        if len(self.queue) > self.chunk_size:
            self.insert_data()
            return True
        else:
            return False 

    def flatten_pyads_struct(self, d: tuple, parent_key='', sep='.') -> list:
        items = []
        for t in d:
            name = t[0]
            type = t[1]
            length = t[2]
            new_key = f"{parent_key}{sep}{name}" if parent_key else name
            if isinstance(type, tuple):
                for i in range(length):
                    if length > 1:
                        k = f"{new_key}_{i}"
                    else:
                        k = new_key
                    items.extend(self.flatten_pyads_struct(type, k, sep))
            else:
                for i in range(length):
                    if length > 1:
                        k = f"{new_key}_{i}" 
                    else:
                        k = new_key
                    
                    items.append((k, ctsDataType[type.__name__].value, length))
        return items
    
    def flatten_value(self, d) -> list:
        items = []
        for k, v in d.items():
            if isinstance(v, dict):  # OrderedDict も isinstance(dict) で判定可能
                items.extend(self.flatten_value(v))
            elif k != "timestamp":
                if isinstance(v, list):
                    for i in range(len(v)):
                        items.append(v[i])
                else:
                    items.append(v)
        return items



    @abstractmethod
    def insert_data(self, session : Session):
        pass

    def q_size(self):
        return len(self.queue)


class MultiTimeSeries(IoTTimeSeriesBase):
    
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.plc_data_model, tuple) or len(self.plc_data_model) <= 1 or not isinstance(self.plc_data_model[0], tuple):
            raise ValueError("plc_data_model must be a tuple of tuples for MultiTimeSeries")
        self.measurements_list = self.flatten_pyads_struct(self.plc_data_model)
        
    @SessionManagement.session
    def create_aligned_time_series(self, session : Session):
        try:
            if isinstance(self.plc_data_model, tuple) and len(self.plc_data_model) > 1 and isinstance(self.plc_data_model[0], tuple):
                ts_path_list = [f"{self.storage_group_name}.{self.time_series_name}.{item[0]}" for item in self.measurements_list]
                ts_type_list = [item[1] for item in self.measurements_list]
                encoding_lst = [TSEncoding.PLAIN for _ in range(len(ts_path_list))]
                compressor_lst = [Compressor.SNAPPY for _ in range(len(ts_path_list))]
                session.create_multi_time_series(
                    ts_path_list, ts_type_list, encoding_lst, compressor_lst
                )
            else:
                raise ValueError("plc_data_model must be a tuple of tuples for MultiTimeSeries")
            print(f"Created aligned time series: {self.storage_group_name}.{self.time_series_name} with measurements {self.measurements_list}")
        except StatementExecutionException as e:
            print(f"Time series already exists: {self.storage_group_name}.{self.time_series_name}")
        
    @SessionManagement.session
    def insert_data(self, session : Session):
        try:
            if isinstance(self.plc_data_model, tuple) and len(self.plc_data_model) > 1 and isinstance(self.plc_data_model[0], tuple):
                chunk = list(self.queue)
                chunk_value = [self.flatten_value(d) for d in chunk]
                self.queue.clear()
            else:
                raise ValueError("plc_data_model must be a tuple of tuples for MultiTimeSeries")
            measurements_name_list = [i[0] for i in self.measurements_list]
            times_list = np.array([int(r["timestamp"].timestamp() * 10**6) for r in chunk],  TSDataType.INT64.np_dtype())
            data_types = [i[1] for i in self.measurements_list]
            values_list = [
                np.array([l[i] for l in chunk_value], data_types[i].np_dtype()) 
                for i, v in enumerate(self.measurements_list)
            ]


            tablet = NumpyTablet(
                f"{self.storage_group_name}.{self.time_series_name}",
                measurements_name_list,
                data_types,
                values_list,
                times_list
            )
            
            session.insert_tablet(tablet)
        except Exception as e:
            raise IoTDBConnectionError("Failed to insert data into IoTDB") from e


class SingleTimeSeries(IoTTimeSeriesBase):

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.plc_data_model, tuple) and len(self.plc_data_model) > 1 and isinstance(self.plc_data_model[0], tuple):
            raise ValueError("plc_data_model must be a single type for SingleTimeSeries")
        
        self.measurements_list = [(self.time_series_name, ctsDataType[self.plc_data_model.__name__].value, 1)]


    @SessionManagement.session
    def create_aligned_time_series(self, session : Session):
        pass
        try:
            if isinstance(self.plc_data_model, tuple) and len(self.plc_data_model) > 1 and isinstance(self.plc_data_model[0], tuple):
                raise ValueError("plc_data_model must be a single type for SingleTimeSeries")
            else:
                session.create_time_series(
                    f"{self.storage_group_name}.{self.time_series_name}", 
                    ctsDataType[self.plc_data_model.__name__].value, 
                    TSEncoding.PLAIN, 
                    Compressor.SNAPPY
                )
            print(f"Created aligned time series: {self.storage_group_name}.{self.time_series_name}")
        except StatementExecutionException as e:
            print(f"Time series already exists: {self.storage_group_name}.{self.time_series_name}")

    @SessionManagement.session
    def insert_data(self, session : Session):
        try:
            if isinstance(self.plc_data_model, tuple) and len(self.plc_data_model) > 1 and isinstance(self.plc_data_model[0], tuple):
                raise ValueError("plc_data_model must be a single type for SingleTimeSeries")
            else:
                chunk = list(self.queue)
                self.queue.clear()
            times_list = np.array([int(r["timestamp"].timestamp() * 10**6) for r in chunk],  TSDataType.INT64.np_dtype())
            data_types = [i[1] for i in self.measurements_list]
            ts_datatype = ctsDataType[self.plc_data_model.__name__].value
            values_list = np.array([self.flatten_value(r) for r in chunk], ts_datatype.np_dtype())
            tablet = NumpyTablet(
                f"{self.storage_group_name}",
                [self.time_series_name],
                data_types,
                [values_list],
                times_list
            )
            session.insert_tablet(tablet)
        except Exception as e:
            raise IoTDBConnectionError("Failed to insert data into IoTDB") from e
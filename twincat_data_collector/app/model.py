import pyads
from error_handler import AdsConnectionError
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Tuple, List, Union, TypeVar
from ads_communication import AdsPortConnection
from iotdb_utils import IoTTimeSeriesBase, SingleTimeSeries, MultiTimeSeries, IoTDBClientSession
import asyncio

T = TypeVar('T', bound=Union[Tuple[Tuple], pyads.PLCTYPE_BOOL, pyads.PLCTYPE_BYTE, pyads.PLCTYPE_DWORD, pyads.PLCTYPE_INT, pyads.PLCTYPE_DINT, pyads.PLCTYPE_LINT, pyads.PLCTYPE_UDINT, pyads.PLCTYPE_ULINT, pyads.PLCTYPE_REAL, pyads.PLCTYPE_LREAL, pyads.PLCTYPE_STRING, pyads.PLCTYPE_WSTRING])

@dataclass
class EventTaskBase(ABC):
    """ADS Notification event handler abstruct class"""
    subscriber : AdsPortConnection
    mapping_model : T
    watch_symbol : str
    queue : asyncio.Queue = field(default=None)

    def __post_init__(self):
        publisher = self.subscriber.reg_notification(symbol=self.watch_symbol, model=self.mapping_model)
        self.queue = publisher.queue

    @abstractmethod
    async def observer(self):
        pass

    async def observer_task(self):
        while True:
            await self.observer()
            
@dataclass
class IoTDBRecorder(EventTaskBase):
    time_series_manager : IoTTimeSeriesBase = field(default=None, init=True)
    
    """IoTDB recorder"""
    def __post_init__(self):
        super().__post_init__()

    async def observer(self) -> bool:
        data_count = 0
        while not self.queue.empty():
            data_count += 1
            record = await self.queue.get()
            record["timestamp"] = record["timestamp"].astimezone(ZoneInfo("Japan"))
            new_record = {i: record[i] for i in record if isinstance(record[i], (int, float, bool, str, datetime))}
            if self.time_series_manager.write_data(new_record):
                break
        print(f"{self.watch_symbol} data write count : {data_count}/{self.time_series_manager.chunk_size}")
        if  self.queue.qsize() > 0:
            self.time_series_manager.chunk_size += self.queue.qsize()
        elif self.time_series_manager.chunk_size > data_count:
            self.time_series_manager.chunk_size -= (self.time_series_manager.chunk_size - data_count)
        await asyncio.sleep(1)
        return data_count > 0


@dataclass
class TwinCATStructSymbol:
    type_def: Tuple
    symbols : List[str] = field(default_factory=list)



import pyads
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Tuple, List
from ads_communication import AdsCommunication, EventReporter
from iotdb_utils import IoTTimeSeries, IoTDBClientSession
import asyncio

@dataclass
class IEventTask(ABC):
    @abstractmethod
    async def observable(self):
        pass


@dataclass
class BaseEventTask(IEventTask):
    """ADS Notification event handler abstruct class"""
    ads_connection : AdsCommunication
    mapping_model : tuple = field(default_factory=tuple)
    watch_symbol : str = field(default_factory=str)
    reconnect : bool = field(default_factory=bool)

    def create_notification(self):
        self.event_handler = EventReporter(plc=self.ads_connection,
                                         mapping_structure=self.mapping_model,
                                         mapping_symbol=self.watch_symbol,
                                         packkaged_num=1)

    async def observer_task(self):
        while True:
            if await self.observable():
                self.reconnect = False

    async def alive_check_task(self):
       while True:
           if self.reconnect:
                print(f"{self.watch_symbol} : Connection lost. Attempting to reconnect...")
                self.ads_connection.port_close()
                await asyncio.sleep(1)  # Wait before trying to reconnect
                self.ads_connection.port_open()
           try:
               if self.ads_connection.connection.is_open:
                    module_state = self.ads_connection.connection.read_state()
                    print(f"Port {self.ads_connection.ads_port} : ADS State {module_state[0]}, Device state : {module_state[1]}")
                    if (module_state[0] != 5 or module_state[1] != 0):
                        print(f"{self.watch_symbol} : Watch Dog Error")
                        self.reconnect = True
               else:
                   print(f"{self.watch_symbol} : Could not open.")
                   self.reconnect = True
           except pyads.pyads_ex.ADSError as e:
               print(f"{self.watch_symbol} : ADSError : {e}")
               self.reconnect = True
           await asyncio.sleep(10)  # Check every 10 seconds


@dataclass
class IIoTDB(ABC):
    time_series_manager : IoTTimeSeries = field(init=True)
 

@dataclass
class ConcreteEventRecord(BaseEventTask, IIoTDB):

    """IoTDB recorder"""
    def __post_init__(self):
        self.create_notification()

    async def observable(self):
        data_count = 0
        while not self.event_handler.queue.empty():
            data_count += 1
            record = await self.event_handler.queue.get()
            record["timestamp"] = record["timestamp"].astimezone(ZoneInfo("Japan"))
            new_record = {i: record[i] for i in record if isinstance(record[i], (int, float, bool, str, datetime))}
            if self.time_series_manager.write_data(new_record):
                break
        print(f"Job data write count : {data_count}/{self.time_series_manager.chunk_size}")
        if  self.event_handler.queue.qsize() > 0:
            self.time_series_manager.chunk_size += self.event_handler.queue.qsize()
        elif self.time_series_manager.chunk_size > data_count:
            self.time_series_manager.chunk_size -= (self.time_series_manager.chunk_size - data_count)
        await asyncio.sleep(1)
        return data_count > 0


@dataclass
class TwinCATStructSymbol:
    type_def: Tuple
    symbols : List[str] = field(default_factory=list)



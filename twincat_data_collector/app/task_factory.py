from dataclasses import dataclass, field
import asyncio
import os
from ads_communication import AdsPortConnection
from iotdb_utils import IoTDBClientSession, IoTTimeSeriesBase, MultiTimeSeries, SingleTimeSeries
from model import EventTaskBase, IoTDBRecorder
from typing import TypeVar, Union, Tuple
import pyads
from abc import ABC, abstractmethod
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
)

logger = logging.getLogger(__name__)



T = TypeVar('T', bound=Union[Tuple[Tuple], pyads.PLCTYPE_BOOL, pyads.PLCTYPE_BYTE, pyads.PLCTYPE_DWORD, pyads.PLCTYPE_INT, pyads.PLCTYPE_DINT, pyads.PLCTYPE_LINT, pyads.PLCTYPE_UDINT, pyads.PLCTYPE_ULINT, pyads.PLCTYPE_REAL, pyads.PLCTYPE_LREAL, pyads.PLCTYPE_STRING, pyads.PLCTYPE_WSTRING])

@dataclass
class IEventTaskFactory(ABC):
    products : list = field(default_factory=list)
    
    def create(self, 
               ads_port_connection : AdsPortConnection,
               iotdb_session : IoTDBClientSession,
               twincat_datatype : T,
               twincat_symbol : str,
               time_series_name : str,
               chunk_size : int,
               storage_group_name : str,
               cycle_time: int,
               max_delay: int,
               fixed_period: bool
               ) -> EventTaskBase:
        p = self.create_product(
            ads_port_connection=ads_port_connection,
            iotdb_session=iotdb_session,
            twincat_datatype=twincat_datatype,
            twincat_symbol=twincat_symbol,
            time_series_name=time_series_name,
            chunk_size=chunk_size,
            storage_group_name=storage_group_name,
            cycle_time=cycle_time,
            max_delay=max_delay,
            fixed_period=fixed_period
        )
        self.products.append(p)
        return p

    def remove(self, product: EventTaskBase):
        if product in self.products:
            self.products.remove(product)

    @abstractmethod
    def create_product(self, 
               ads_port_connection : AdsPortConnection,
               iotdb_session : IoTDBClientSession,
               twincat_datatype : T,
               twincat_symbol : str,
               time_series_name : str,
               chunk_size : int,
               storage_group_name : str,
               cycle_time: int,
               max_delay: int,
               fixed_period: bool
               ) -> EventTaskBase:
        pass

@dataclass
class EventTaskFactory(IEventTaskFactory):
    

    def create_product(self, 
               ads_port_connection : AdsPortConnection,
               iotdb_session : IoTDBClientSession,
               twincat_datatype : T,
               twincat_symbol : str,
               storage_group_name : str,
               time_series_name : str,
               chunk_size : int,
               cycle_time : int = 1,
               max_delay : int = 100,
               fixed_period : bool = False
               ) -> EventTaskBase:
        if isinstance(twincat_datatype, tuple):
            logging.info(f"Create gateway as Structure for {twincat_symbol}, data type : {type(twincat_datatype)}")
            time_series = MultiTimeSeries(
                session_manager=iotdb_session,
                plc_data_model=twincat_datatype, 
                storage_group_name=storage_group_name,
                time_series_name=time_series_name,
                chunk_size = chunk_size
                )
            time_series.create_aligned_time_series()
            
            return IoTDBRecorder(
                subscriber=ads_port_connection,
                mapping_model=twincat_datatype,
                watch_symbol=twincat_symbol,
                time_series_manager=time_series,
                cycle_time=cycle_time,
                max_delay=max_delay,
                fixed_period=fixed_period
            )
        else:
            logging.info(f"Create gateway as primitive type for {twincat_symbol}, data type : {type(twincat_datatype)}")
            time_series = SingleTimeSeries(
                session_manager=iotdb_session, 
                plc_data_model=twincat_datatype, 
                storage_group_name=storage_group_name,
                time_series_name=time_series_name,
                chunk_size = chunk_size
                )
            time_series.create_aligned_time_series()
            
            return IoTDBRecorder(
                subscriber=ads_port_connection,
                mapping_model=twincat_datatype,
                watch_symbol=twincat_symbol,
                time_series_manager=time_series,
                cycle_time=cycle_time,
                max_delay=max_delay,
                fixed_period=fixed_period
            )

class ADSEventWatchTaskManager:
    task_queue : asyncio.Queue = asyncio.Queue()
    factory = EventTaskFactory()
    tg : asyncio.TaskGroup
    
    @classmethod
    def create_event_task(cls,
                          ads_port_connection : AdsPortConnection,
                          iotdb_session : IoTDBClientSession,
                          twincat_datatype : T,
                          twincat_symbol : str,
                          storage_group_name : str,
                          time_series_name : str,
                          chunk_size : int,
                          cycle_time: int = 1,
                          max_delay: int = 100,
                          fixed_period: bool = False
                          ):
        
        try:
            event_task = cls.factory.create(
                ads_port_connection=ads_port_connection,
                iotdb_session=iotdb_session,
                twincat_datatype=twincat_datatype,
                twincat_symbol=twincat_symbol,
                storage_group_name=storage_group_name,
                time_series_name=time_series_name,
                chunk_size=chunk_size,
                cycle_time=cycle_time,
                max_delay=max_delay,
                fixed_period=fixed_period
            )
            cls.task_queue.put_nowait(event_task.observer_task())
            if [p.subscriber for p in cls.factory.products].count(ads_port_connection) < 2:
                cls.task_queue.put_nowait(ads_port_connection.alive_check_task())
            logging.info(f"Event task created for symbol: {event_task.watch_symbol}")
        except pyads.pyads_ex.ADSError as e:
            logging.error(f"Failed to create event task for symbol: {twincat_symbol}. Error: {e}")

    @classmethod
    def task_run(cls):
        async def main():
            try:
                logging.warning(f"{__name__} Start")
                async with asyncio.TaskGroup() as cls.tg:
                    while True:
                        callable = await cls.task_queue.get()
                        cls.tg.create_task(callable)
                logging.warning(f"{__name__} Finish")
            except Exception as e:
                logging.error(f"Error in task_run: {e}")
                for task in cls.tg._tasks:
                    task.cancel()
                raise
        asyncio.run(main())
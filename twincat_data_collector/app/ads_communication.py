import pyads
import ctypes
from dataclasses import dataclass, field
from typing import Tuple, Callable, TypeVar, Union
from zoneinfo import ZoneInfo
import asyncio
from abc import ABC, abstractmethod
from error_handler import AdsConnectionError

T = TypeVar('T', bound=Union[Tuple[Tuple], pyads.PLCTYPE_BOOL, pyads.PLCTYPE_BYTE, pyads.PLCTYPE_DWORD, pyads.PLCTYPE_INT, pyads.PLCTYPE_DINT, pyads.PLCTYPE_LINT, pyads.PLCTYPE_UDINT, pyads.PLCTYPE_ULINT, pyads.PLCTYPE_REAL, pyads.PLCTYPE_LREAL, pyads.PLCTYPE_STRING, pyads.PLCTYPE_WSTRING])


@dataclass
class AbstructAdsDeviceNotification(ABC):
    connection: pyads.Connection
    symbol: str
    model: T
    alive_report: callable
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    subscriber: Callable = field(default=None)
    cycle_time : int = field(default=1)
    state : bool = field(default=False)

    def __post_init__(self):
        if self.queue is None:
            self.queue = asyncio.Queue()
        self.connection = self.connection
        self.connection.auto_update = True
        self.set_notification()


    @abstractmethod
    def create_notification(self):
        pass

    def set_notification(self):
        try:
            self.create_notification()
            self.state = True
        except pyads.pyads_ex.ADSError as e:
            raise AdsConnectionError(f"Symbol not found: {self.symbol}: {e}") from e
            self.state = False


@dataclass
class AdsDeviceNotificationStructure(AbstructAdsDeviceNotification):
    
    def __post_init__(self):
        if self.subscriber is None:
            self.subscriber = self.default_subscriber
        super().__post_init__()
        
    def create_notification(self):
        if isinstance(self.model, tuple) and len(self.model) > 1 and isinstance(self.model[0], tuple):
            size_of_struct = pyads.size_of_structure(self.model)
            attr = pyads.NotificationAttrib(size_of_struct)
            attr.trans_mode = pyads.ADSTRANS_SERVERONCHA
            attr.max_delay = 100
            attr.cycle_time = self.cycle_time
            @self.connection.notification(ctypes.c_ubyte * size_of_struct)
            def callback(handle, name, timestamp, value):
                timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
                self.subscriber(timestamp, value)
                self.alive_report()
            self.connection.add_device_notification(self.symbol,
                                        attr,
                                        callback)

    def default_subscriber(self, timestamp, value):
        data = pyads.dict_from_bytes(value, self.model)
        data["timestamp"] = timestamp
        self.queue.put_nowait(data)

@dataclass
class AdsDeviceNotificationPrimitive(AbstructAdsDeviceNotification):
    
    def __post_init__(self):
        if self.subscriber is None:
            self.subscriber = self.default_subscriber
        super().__post_init__()

    def create_notification(self):
            attr = pyads.NotificationAttrib(ctypes.sizeof(self.model))
            attr.trans_mode = pyads.ADSTRANS_SERVERONCHA
            attr.max_delay = 100
            attr.cycle_time = self.cycle_time

            @self.connection.notification(self.model)
            def callback(handle, name, timestamp, value):
                timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
                self.subscriber(timestamp, {name: value})
                self.alive_report()
            self.connection.add_device_notification(self.symbol,
                                        attr,
                                        callback)
    
    def default_subscriber(self, timestamp, value):
        value["timestamp"] = timestamp
        self.queue.put_nowait(value)


@dataclass
class AdsPortConnection:
    ams_net_id: str = field(default='127.0.0.1.1.1')
    ads_port: int = field(default=851)
    connection: pyads.Connection = field(default=None, init=False)
    symbols: list = field(default_factory=list, init=False)
    watchdog: bool = field(default=False, init=False)
    
    def __post_init__(self):
        self.publishers = list()
        print(f"Connecting to PLC with AMS ID: {self.ams_net_id}, Port: {self.ads_port}")
        self.connection = pyads.Connection(self.ams_net_id, self.ads_port)
        self.port_open()
    
    async def reconnect(self):
        self.port_close()
        await asyncio.sleep(1)  # Wait before trying to reconnect
        self.port_open()
    
    def reconnect_nowait(self):
        asyncio.create_task(self.reconnect())
    
    def port_open(self):
        try:
            self.connection.open()
            
            self.symbols = self.connection.get_all_symbols()
            #for symbol in self.symbols:
            #    print(symbol.name, symbol.plc_type)
            #    if symbol.is_structure:
            #        print(f"{symbol.name} is a structure with size {symbol.struct_size}")
            
            if len(self.publishers) > 0:
                for publisher in self.publishers:
                    publisher.set_notification()
            
            
                        
        except pyads.pyads_ex.ADSError as e:
            raise AdsConnectionError(f"Failed to open ADS connection. target : {self.ams_net_id}, target port : {self.ads_port}") from e
              
        except RuntimeError as e:
            raise AdsConnectionError(f"No route to machine. Check your network configuration. router: {self.router_address}, target : {self.ams_net_id}, target port : {self.ads_port}") from e
            
    def reg_notification(self, symbol: str, model: T, cycle_time: int = 1, subscriber: Callable = None) -> AbstructAdsDeviceNotification:
        if isinstance(model, tuple) and len(model) > 1 and isinstance(model[0], tuple):
            publisher = AdsDeviceNotificationStructure(
                    connection=self.connection,
                    model=model,
                    alive_report=self.alive_report,
                    subscriber=subscriber,
                    symbol=symbol,
                    cycle_time=cycle_time
                )
        else:
            publisher = AdsDeviceNotificationPrimitive(
                    connection=self.connection,
                    model=model,
                    alive_report=self.alive_report,
                    subscriber=subscriber,
                    symbol=symbol,
                    cycle_time=cycle_time
                )
        self.publishers.append(publisher)
        return publisher

    def write(self,symbol: str, value, type):
        self.connection.write_by_name(symbol, value, type)    

    def port_close(self):
        for publisher in self.publishers:
            publisher.status = False
        self.connection.close()

    def disconnect(self):
        self.connection.close()

    def alive_report(self):
        self.watchdog = True
        
    async def alive_check_task(self):
        while True:
            try:
                if not self.watchdog:
                    print(f"Connection lost. Attempting to reconnect...")
                    await self.reconnect()
                if self.connection.is_open:
                    module_state = self.connection.read_state()
                    print(f"Port {self.ads_port} : ADS State {module_state[0]}, Device state : {module_state[1]}")
                    if (module_state[0] != 5 or module_state[1] != 0):
                        self.watchdog = False
                else:
                    print(f"Port {self.ads_port} : Could not open.")
                    self.watchdog = False
            except (pyads.pyads_ex.ADSError, AdsConnectionError) as e:
                print(f"Port {self.ads_port} : ADSError : {e}")
                self.watchdog = False
            await asyncio.sleep(10)  # Check every 10 seconds
from dataclasses import dataclass, field
import asyncio
from model import ConcreteEventRecord
from plc_data_types import job_event_structure, axis_to_plc_structure
from ads_communication import AdsCommunication, EventReporter
import pandas as pd
import os
from iotdb_utils import IoTTimeSeries, IoTDBClientSession


@dataclass
class TwinCATData:
    motion_observer : ConcreteEventRecord = field(default = None)
    job_observer    : ConcreteEventRecord = field(default = None)

    def __post_init__(self):
        ams_net_id = os.getenv('TARGET_AMSID', default='127.0.0.1.1.1')
        router = os.getenv('ROUTER_ADDRESS', default='127.0.0.1')

        self.motion_connector = AdsCommunication(ams_net_id=ams_net_id,
                                    ads_port=501,
                                    router_address=router)

        self.plc_connector = AdsCommunication(ams_net_id=ams_net_id,
                                    ads_port=851,
                                    router_address=router)

        self.iotdb_session_manager = IoTDBClientSession(host=os.getenv('IOTDB_HOST', default='127.0.0.1'))
        self.motion_time_series = IoTTimeSeries(
            self.iotdb_session_manager,
            plc_data_model=axis_to_plc_structure, 
            storage_group_name="root.demo1",
            time_series_name="axis1",
            chunk_size = 500
            )
        self.motion_time_series.create_aligned_time_series()

        self.job_time_series = IoTTimeSeries(
            self.iotdb_session_manager, 
            plc_data_model=job_event_structure, 
            storage_group_name="root.demo1",
            time_series_name="job",
            chunk_size = 1
            )
        self.job_time_series.create_aligned_time_series()

    async def data_collection_task(self):
        self.motion_observer = ConcreteEventRecord(
            ads_connection=self.motion_connector,
            mapping_model=axis_to_plc_structure,
            watch_symbol='Axes.Axis 1.ToPlc',
            time_series_manager=self.motion_time_series
        )

        self.job_observer = ConcreteEventRecord(
            ads_connection=self.plc_connector,
            mapping_model=job_event_structure,
            watch_symbol='demo3.runner.event_message',
            time_series_manager=self.job_time_series
            
        )

        await asyncio.gather(
            self.motion_observer.observer_task(),
            self.job_observer.observer_task(),
            self.motion_observer.alive_check_task(),
            self.job_observer.alive_check_task()
        )


def main():    
    twincat = TwinCATData()
    asyncio.run(twincat.data_collection_task())

if __name__ == '__main__':
    main()

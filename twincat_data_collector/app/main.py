import logging
from task_factory import ADSEventWatchTaskManager
from ads_communication import AdsPortConnection
from iotdb_utils import IoTDBClientSession
from plc_data_types import job_event_structure, axis_to_plc_structure
from error_handler import AdsConnectionError, IoTDBConnectionError
import pyads
import os


ams_net_id = os.getenv('TARGET_AMSID', default='199.4.42.250.1.1')
router = os.getenv('ROUTER_ADDRESS', default='127.0.0.1')

try:
    motion_connector = AdsPortConnection(ams_net_id=ams_net_id,
                                ads_port=501)
    plc_connector = AdsPortConnection(ams_net_id=ams_net_id,
                                ads_port=851)

    iotdb_session_manager = IoTDBClientSession(host=os.getenv('IOTDB_HOST', default='127.0.0.1'))

    ADSEventWatchTaskManager.create_event_task(
        ads_port_connection=plc_connector,
        iotdb_session=iotdb_session_manager,
        twincat_datatype=job_event_structure,
        twincat_symbol='demo3.runner.event_message',
        storage_group_name="root.demo1",
        time_series_name='job',
        chunk_size=1
    )

    ADSEventWatchTaskManager.create_event_task(
        ads_port_connection=plc_connector,
        iotdb_session=iotdb_session_manager,
        twincat_datatype=pyads.PLCTYPE_UINT,
        twincat_symbol='demo3._state',
        storage_group_name="root.demo1",
        time_series_name='machine_state',
        chunk_size=1
    )
    
    ADSEventWatchTaskManager.create_event_task(
        ads_port_connection=motion_connector,
        iotdb_session=iotdb_session_manager,
        twincat_datatype=axis_to_plc_structure,
        twincat_symbol='Axes.Axis 1.ToPlc',
        storage_group_name="root.demo1",
        time_series_name="axis1",
        chunk_size=500
    )
except AdsConnectionError as e:
    logging.info(e)
    exit(1)

except IoTDBConnectionError as e:
    logging.info(e)
    exit(1)

ADSEventWatchTaskManager.task_run()


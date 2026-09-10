import logging
from task_factory import ADSEventWatchTaskManager
from ads_communication import AdsPortConnection
from iotdb_utils import IoTDBClientSession
from plc_data_types import xts_mover_controller, xts_motor_module_alarm_structure, xts_motor_module_latest_message, xts_motor_module_voltage_current
from error_handler import AdsConnectionError, IoTDBConnectionError
import pyads
import os
import csv

# ADS設定
ams_net_id = os.getenv('TARGET_AMSID', default='10.1.177.22.1.1')
router = os.getenv('ROUTER_ADDRESS', default='127.0.0.1')


def read_def(file) -> list:
    with open(file, newline = "") as f:
        r = csv.DictReader(f, delimiter=",", quotechar='"')
        return [i for i in r]
    f.close()

# CSVファイル読み込み
mover_template = read_def('./xts_mover_data_acquisition_def.csv')
motor_template = read_def('./xts_motor_data_acquisition_def.csv')

watch_movers = range(1,13)
watch_motors = range(1,33)

try:
    xts_connector = AdsPortConnection(ams_net_id=ams_net_id,ads_port=350)
    iotdb_session_manager = IoTDBClientSession(host=os.getenv('IOTDB_HOST', default='127.0.0.1'))

    def create_watcher(data: list, unit : int, macro: str):
        for r in data:
            logging.debug(r)
            if int(r['enable']) != 1:
                continue
            type_obj = globals().get(r['tc_datatype'])
            
            symbol = r['twincat_symbol'].replace(f"{{{macro}}}", str(unit))
            storage_group = r['storage_group_name'].replace(f"{{{macro}}}", str(unit))
            
            if type_obj is not None:
                ADSEventWatchTaskManager.create_event_task(
                        ads_port_connection=xts_connector,
                        iotdb_session=iotdb_session_manager,
                        twincat_datatype=type_obj,
                        twincat_symbol=symbol,
                        storage_group_name=storage_group,
                        time_series_name=r['time_series_name'],
                        chunk_size=int(r['chunk_size']),
                        cycle_time=int(r['cycle_time']),
                        max_delay=int(r['max_delay']),
                        fixed_period=True
                    )           
            else:
                ADSEventWatchTaskManager.create_event_task(
                        ads_port_connection=xts_connector,
                        iotdb_session=iotdb_session_manager,
                        twincat_datatype=getattr(pyads,r['tc_datatype']),
                        twincat_symbol=symbol,
                        storage_group_name=storage_group,
                        time_series_name=r['time_series_name'],
                        chunk_size=int(r['chunk_size']),
                        cycle_time=int(r['cycle_time']),
                        max_delay=int(r['max_delay']),
                        fixed_period=True
                    )        


    for n_mover in watch_movers:
        create_watcher(mover_template,n_mover, 'mover_num')
    
    for n_motor in watch_motors:
        create_watcher(motor_template,n_motor, 'module_num')


    
except AdsConnectionError as e:
    logging.info(e)
    exit(1)

except IoTDBConnectionError as e:
    logging.info(e)
    exit(1)

ADSEventWatchTaskManager.task_run()


import pyads


# Alarm event framework
alarm_structure = (
    ("nSourceId", pyads.PLCTYPE_UDINT, 1),
    ("nEventId", pyads.PLCTYPE_UDINT, 1),
    ("Severity", pyads.PLCTYPE_WSTRING, 1, 17),
    ("ConfirmState", pyads.PLCTYPE_WSTRING, 1, 5),
    ("sDate", pyads.PLCTYPE_STRING, 1, 23),
    ("sTime", pyads.PLCTYPE_STRING, 1, 23),
    ("Computer", pyads.PLCTYPE_WSTRING, 1, 80),
    ("sSource", pyads.PLCTYPE_WSTRING, 1, 255),
    ("MessageText", pyads.PLCTYPE_WSTRING, 1, 255),
    ("bQuitMessage", pyads.PLCTYPE_BOOL, 1),
    ("bConfirmable", pyads.PLCTYPE_BOOL, 1)
)

# Job framework
job_event_structure = (
    ("subject", pyads.PLCTYPE_STRING, 1, 255),
    ("job_namespace", pyads.PLCTYPE_STRING, 1, 255),
    ("job_id", pyads.PLCTYPE_STRING, 1, 255),
    ("old_state", pyads.PLCTYPE_STRING, 1, 16),
    ("new_state", pyads.PLCTYPE_STRING, 1, 16),
    ("num_of_job", pyads.PLCTYPE_UINT, 1),
    ("record_time", pyads.PLCTYPE_ULINT, 1)
)

# NC PTP axis to_plc

axis_to_plc_structure=(
    ("StateDWord", pyads.PLCTYPE_DWORD,1),
    ("ErrCode", pyads.PLCTYPE_UDINT,1),
    ("AxisState", pyads.PLCTYPE_UDINT,1),
    ("AxisModeConfirmation", pyads.PLCTYPE_UDINT,1),
    ("HomingState", pyads.PLCTYPE_UDINT,1),
    ("CoupleState", pyads.PLCTYPE_UDINT,1),
    ("SvbEntries", pyads.PLCTYPE_UDINT,1),
    ("SafEntries", pyads.PLCTYPE_UDINT,1),
    ("AxisId", pyads.PLCTYPE_UDINT,1),
    ("OpModeDWord", pyads.PLCTYPE_UDINT,1),
    ("ActPos", pyads.PLCTYPE_LREAL,1),
    ("ActPosModulo", pyads.PLCTYPE_LREAL,1),
    ("ActiveControlLoopIndex", pyads.PLCTYPE_UINT,1),
    ("ControlLoopIndex", pyads.PLCTYPE_UINT,1),
    ("ModloActTurns", pyads.PLCTYPE_DINT,1),
    ("ActVelo", pyads.PLCTYPE_LREAL,1),
    ("PosDiff", pyads.PLCTYPE_LREAL,1),
    ("SetPos", pyads.PLCTYPE_LREAL,1),
    ("SetVelo", pyads.PLCTYPE_LREAL,1),
    ("SetAcc", pyads.PLCTYPE_LREAL,1),
    ("TargetPos", pyads.PLCTYPE_LREAL,1),
    ("ModuloSetPos", pyads.PLCTYPE_LREAL,1),
    ("ModloSetTurns", pyads.PLCTYPE_DINT,1),
    ("CmdNo", pyads.PLCTYPE_UINT,1),
    ("CmdState", pyads.PLCTYPE_UINT,1),
    ("SetJerk", pyads.PLCTYPE_LREAL,1),
    ("SetTorque", pyads.PLCTYPE_LREAL,1),
    ("ActTorque", pyads.PLCTYPE_LREAL,1),
    ("StateDWord2", pyads.PLCTYPE_DWORD,1),
    ("StateDWord3", pyads.PLCTYPE_DWORD,1),
    ("TouchProbeState", pyads.PLCTYPE_DWORD,1),
    ("TouchProbeCounter", pyads.PLCTYPE_DWORD,1),
    ("CamCouplingState", pyads.PLCTYPE_SINT,8),
    ("CamCouplingTableID", pyads.PLCTYPE_UINT,8),
    ("ActTorqueDerivative", pyads.PLCTYPE_LREAL,1),
    ("SetTorqueDerivative", pyads.PLCTYPE_LREAL,1),
    ("AbsPhasingPos", pyads.PLCTYPE_LREAL,1),
    ("TorqueOffset", pyads.PLCTYPE_LREAL,1),
    ("ActPosWithoutPosCorrection", pyads.PLCTYPE_LREAL,1),
    ("ActAcc", pyads.PLCTYPE_LREAL,1),
    ("DcTimeStamp", pyads.PLCTYPE_UDINT,1),
    ("_reserved2", pyads.PLCTYPE_USINT,4),
    ("UserData", pyads.PLCTYPE_LREAL,1),
)

xplanar_actual_position = (
    ('x', pyads.PLCTYPE_LREAL, 1),
    ('y', pyads.PLCTYPE_LREAL, 1),
    ('z', pyads.PLCTYPE_LREAL, 1),
    ('a', pyads.PLCTYPE_LREAL, 1),
    ('b', pyads.PLCTYPE_LREAL, 1),
    ('c', pyads.PLCTYPE_LREAL, 1)
)

xplanar_actual_velocity=(
    ('x', pyads.PLCTYPE_LREAL, 1),
    ('y', pyads.PLCTYPE_LREAL, 1),
    ('z', pyads.PLCTYPE_LREAL, 1),
    ('a', pyads.PLCTYPE_LREAL, 1),
    ('b', pyads.PLCTYPE_LREAL, 1),
    ('c', pyads.PLCTYPE_LREAL, 1)
)

xplanar_aps_diag=(
    ('identity', pyads.PLCTYPE_USINT, 1),
    ('dc_link_voltage', pyads.PLCTYPE_DINT, 1),
    ('power_supply_current', pyads.PLCTYPE_DINT, 1),
    ('temperature_north', pyads.PLCTYPE_UINT, 1),
    ('temperature_east', pyads.PLCTYPE_UINT, 1),
    ('temperature_south', pyads.PLCTYPE_UINT, 1),
    ('temperature_west', pyads.PLCTYPE_UINT, 1),
    ('temperature_center', pyads.PLCTYPE_UINT, 1),
    ('temperature_power', pyads.PLCTYPE_UINT, 1),
    ('fan_rpm', pyads.PLCTYPE_UINT, 1),
    ('fan_duty_cycle', pyads.PLCTYPE_USINT, 1),
    ('supply_voltage_us', pyads.PLCTYPE_UDINT, 1),
    ('auxiliary_voltage', pyads.PLCTYPE_UDINT, 1),
    ('acceleration_x', pyads.PLCTYPE_UDINT, 1),
    ('acceleration_y', pyads.PLCTYPE_UDINT, 1),
    ('acceleration_z', pyads.PLCTYPE_UDINT, 1),
    ('fb_fw_rev', pyads.PLCTYPE_UDINT, 1)
)

xplanar_scope_data = (
    ('ActualPositions', pyads.PLCTYPE_LREAL, 6),
    ('PositionError', pyads.PLCTYPE_LREAL, 6),
    ('ActualVelocities', pyads.PLCTYPE_LREAL, 6),
    ('ActualAccelerations', pyads.PLCTYPE_LREAL, 6),
    ('ExternalPositionSetpoints', pyads.PLCTYPE_LREAL, 6),
    ('ExternalVelocitySetpoints', pyads.PLCTYPE_LREAL, 6),
    ('ExternalAccelerationSetpoints', pyads.PLCTYPE_LREAL, 6),
    ('InterpolatedPositionSetpoints', pyads.PLCTYPE_LREAL, 6),
    ('InterpolatedVelocitySetpoints', pyads.PLCTYPE_LREAL, 6),
    ('InterpolatedAccelerationSetpoints', pyads.PLCTYPE_LREAL, 6),
    ('NcDcTimeStamp', pyads.PLCTYPE_ULINT, 1),
    ('OutputForces', pyads.PLCTYPE_LREAL, 6),
    ('ForceLimits', pyads.PLCTYPE_LREAL, 6),
    ('LimitedOutputForces', pyads.PLCTYPE_LREAL, 6),
    ('EstimatedMoverPower', pyads.PLCTYPE_LREAL, 1),
    ('ForceLimitAdaptationFactor', pyads.PLCTYPE_LREAL, 1),
    ('PositionOnCurrentPart', pyads.PLCTYPE_LREAL, 2),
    ('PartOID', pyads.PLCTYPE_UDINT, 1),
    ('MovementAreaOID', pyads.PLCTYPE_UDINT, 1),
    ('MoverCommunicationData', pyads.PLCTYPE_LREAL, 6)
)


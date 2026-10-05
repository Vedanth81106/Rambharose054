%% simulink_mqtt_stream.m

clear;
clc;

model_name = "AeroPistonEngineSimulator";
fault_block = model_name + "/Fault_ID";
onset_block = model_name + "/Degradation/Fault_Onset";

%% Load model + params

load_system(model_name);
engine_params;

%% Settings

simulation_time = 1200;   % 20 minutes
publish_interval = 1.0;   % Publish every 1 second

engine_id = "engine_001";

% Mission profile and mission ID come from the simulation controller
% (environment variables); the defaults reproduce the original run.
profile = string(getenv("SIM_PROFILE"));
if profile == ""
    profile = "cruise";
end

mission_id = string(getenv("SIM_MISSION_ID"));
if mission_id == ""
    mission_id = "mission_001";
end

telemetry_topic = ...
    "engine/" + engine_id + "/telemetry";

fault_topic = ...
    "engine/" + engine_id + "/fault";

%% External inputs

% Throttle, engine load, altitude and ambient temperature over time
% (see mission_profile.m). The model reads t and u from the workspace.
[t, u] = mission_profile(char(profile), simulation_time);

%% Start healthy

% Fault IDs:
%
% 0 = Healthy
% 1 = Misfire
% 2 = Overheating
% 3 = Oil pressure failure
% 4 = Fuel starvation
% 5 = Injector abnormality
% 6 = Cooling degradation
% 7 = CHT sensor drift / failure
% 8 = Combustion instability
% 9 = Abnormal vibration

valid_faults = 0:9;

current_fault = 0;

set_param( ...
    fault_block, ...
    "Value", ...
    num2str(current_fault));

% Fault progression restarts from zero at each injection.
set_param( ...
    onset_block, ...
    "Value", ...
    "0");

%% Create live Simulation object

sm = simulation(model_name);
assignin('base', 't', t);
assignin('base', 'u', u);

sm = setModelParameter( ...
    sm, ...
    StopTime=num2str(simulation_time));

%% Initialize

initialize(sm);

%% Connect to MQTT

% Connect after initialize: compiling the model can take longer than the
% broker's keep-alive window on a first run.
mqtt_host = getenv("MQTT_HOST");
if mqtt_host == ""
    mqtt_host = "127.0.0.1";
end

client = MqttLite(mqtt_host, 1883, "simulink_" + mission_id);
client.subscribe(fault_topic);

fprintf("Connected to MQTT broker at %s.\n", mqtt_host);

fprintf("\n");
fprintf("========================================\n");
fprintf("LIVE SIMULATION STARTED\n");
fprintf("========================================\n");
fprintf("Mission profile: %s\n", profile);
fprintf("Mission ID: %s\n", mission_id);
fprintf("Fault commands: MQTT\n");
fprintf("Fault topic: %s\n", fault_topic);
fprintf("Allowed fault IDs: %s\n", strjoin(string(valid_faults), ", "));
fprintf("========================================\n\n");

%% Main live loop

next_time = publish_interval;

while next_time <= simulation_time

    %% Check MQTT fault command

    % The latest command on the fault topic wins.
    requested_fault = current_fault;
    for msg = client.poll()
        requested_fault = str2double(strtrim(msg.payload));
    end

    %% Validate requested fault

    if requested_fault ~= current_fault

        if ismember(requested_fault, valid_faults)

            current_fault = requested_fault;
            fault_onset = next_time - publish_interval;

            setBlockParameter( ...
                sm, ...
                fault_block, ...
                "Value", ...
                num2str(current_fault));

            setBlockParameter( ...
                sm, ...
                onset_block, ...
                "Value", ...
                num2str(fault_onset));

            fprintf( ...
                "\n>>> FAULT CHANGED TO %d at t=%.0fs <<<\n\n", ...
                current_fault, ...
                fault_onset);

        else

            fprintf( ...
                "\n>>> INVALID FAULT ID: %g <<<\n", ...
                requested_fault);

            fprintf( ...
                ">>> Allowed values: %s <<<\n\n", ...
                strjoin(string(valid_faults), ", "));

        end
    end

    %% Advance simulation

    finished = step( ...
        sm, ...
        PauseTime=next_time);

    %% Get simulation output

    simOut = sm.SimulationOutput;

    telemetry_log = ...
        simOut.telemetry_log;
    %% Extract telemetry
    
    rpm = telemetry_log.signal1.Data;
    fuel_flow = telemetry_log.signal2.Data;
    torque = telemetry_log.signal3.Data;
    oil_temperature = telemetry_log.signal4.Data;
    oil_pressure = telemetry_log.signal5.Data;
    cht = telemetry_log.signal6.Data;
    egt = telemetry_log.signal8.Data;
    vibration = telemetry_log.signal9.Data;
    battery_voltage = telemetry_log.signal10.Data;      % V
    alternator_current = telemetry_log.signal11.Data;   % A
    injection_timing = telemetry_log.signal12.Data;     % deg BTDC
    injection_duration = telemetry_log.signal13.Data;   % ms


    %% External input values

    input_row = min( ...
        round(next_time / (t(2) - t(1))) + 1, ...
        size(u, 1));

    throttle = u(input_row, 1);
    engine_load = u(input_row, 2);
    altitude = u(input_row, 3);
    ambient_temperature = u(input_row, 4);

    %% Get latest values

    rpm = rpm(end);
    fuel_flow = fuel_flow(end);
    torque = torque(end);
    oil_temperature = oil_temperature(end);
    oil_pressure = oil_pressure(end);
    cht = cht(end);
    egt = egt(end);
    vibration = vibration(end);
    battery_voltage = battery_voltage(end);
    alternator_current = alternator_current(end);
    injection_timing = injection_timing(end);
    injection_duration = injection_duration(end);

    %% Real timestamp

    timestamp = datetime( ...
        "now", ...
        "TimeZone", ...
        "UTC");

    timestamp.Format = ...
        "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'";

    %% Build telemetry JSON

    payload = sprintf([ ...
        '{"timestamp":"%s",' ...
        '"engine_id":"%s",' ...
        '"mission_id":"%s",' ...
        '"rpm":%.3f,' ...
        '"torque":%.3f,' ...
        '"cht":%.3f,' ...
        '"egt":%.3f,' ...
        '"oil_pressure":%.3f,' ...
        '"oil_temperature":%.3f,' ...
        '"fuel_flow":%.3f,' ...
        '"vibration":%.3f,' ...
        '"throttle":%.5f,' ...
        '"engine_load":%.5f,' ...
        '"altitude":%.3f,' ...
        '"ambient_temperature":%.3f,' ...
        '"battery_voltage":%.3f,' ...
        '"alternator_current":%.3f,' ...
        '"injection_timing":%.3f,' ...
        '"injection_duration":%.3f,' ...
        '"sim_time":%.1f}' ...
        ], ...
        char(timestamp), ...
        engine_id, ...
        mission_id, ...
        rpm, ...
        torque, ...
        cht, ...
        egt, ...
        oil_pressure, ...
        oil_temperature, ...
        fuel_flow, ...
        vibration, ...
        throttle, ...
        engine_load, ...
        altitude, ...
        ambient_temperature, ...
        battery_voltage, ...
        alternator_current, ...
        injection_timing, ...
        injection_duration, ...
        next_time);
    %% Publish telemetry

    client.publish(telemetry_topic, payload);

    %% Console output

    fprintf( ...
        "t=%4.0fs | fault=%d | RPM=%7.1f | Torque=%5.2f | CHT=%6.1f | EGT=%7.1f | Vbat=%5.2f | Ialt=%5.2f | InjT=%5.2f | InjD=%5.2f\n", ...
        next_time, ...
        current_fault, ...
        rpm, ...
        torque, ...
        cht, ...
        egt, ...
        battery_voltage, ...
        alternator_current, ...
        injection_timing, ...
        injection_duration);

    %% Real-time pacing

    pause(publish_interval);

    next_time = ...
        next_time + publish_interval;

    %% Check completion

    if finished
        break;
    end

end

%% Stop simulation

if sm.Status ~= "inactive"
    stop(sm);
end

%% Disconnect MQTT telemetry client

client.disconnect();

fprintf("\n");
fprintf("========================================\n");
fprintf("LIVE SIMULATION FINISHED\n");
fprintf("========================================\n");
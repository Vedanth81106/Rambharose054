%% simulink_mqtt_stream.m

clear;
clc;

model_name = "AeroPistonEngineSimulator";
fault_block = model_name + "/Fault_ID";

%% Load model + params

load_system(model_name);
engine_params;

%% Settings

simulation_time = 1200;   % 20 minutes
publish_interval = 1.0;   % Publish every 1 second

engine_id = "engine_001";
mission_id = "mission_001";

telemetry_topic = ...
    "engine/" + engine_id + "/telemetry";

fault_topic = ...
    "engine/" + engine_id + "/fault";

%% External inputs

t = (0:0.1:simulation_time)';

u = [
    ones(size(t)), ...
    0.5 * ones(size(t)), ...
    zeros(size(t)), ...
    25 * ones(size(t))
];

%% Start healthy

% Fault IDs:
%
% 0 = Healthy
% 1 = Fault 1
% 2 = Fault 2
% 3 = Fault 3
% 4 = Fault 4

current_fault = 0;

set_param( ...
    fault_block, ...
    "Value", ...
    num2str(current_fault));

%% Connect to MQTT

mqtt = py.importlib.import_module( ...
    'paho.mqtt.client');

client = mqtt.Client();

client.connect( ...
    '127.0.0.1', ...
    int32(1883), ...
    int32(60));

client.loop_start();

fprintf("Connected to MQTT telemetry.\n");

%% Create live Simulation object

sm = simulation(model_name);
assignin('base', 'u', u);

sm = setModelParameter( ...
    sm, ...
    StopTime=num2str(simulation_time));

%% Initialize

initialize(sm);

fprintf("\n");
fprintf("========================================\n");
fprintf("LIVE SIMULATION STARTED\n");
fprintf("========================================\n");
fprintf("Fault commands: MQTT\n");
fprintf("Fault topic: %s\n", fault_topic);
fprintf("Allowed fault IDs: 0, 1, 2, 3, 4\n");
fprintf("========================================\n\n");

%% Main live loop

next_time = publish_interval;

while next_time <= simulation_time

    %% Check MQTT fault command

    requested_fault = str2double( ...
        strtrim(fileread("fault_state.txt")));

    %% Validate requested fault

    if requested_fault ~= current_fault

        if ismember(requested_fault, [0 1 2 3 4])

            current_fault = requested_fault;

            setBlockParameter( ...
                sm, ...
                fault_block, ...
                "Value", ...
                num2str(current_fault));

            fprintf( ...
                "\n>>> FAULT CHANGED TO %d at t=%.0fs <<<\n\n", ...
                current_fault, ...
                next_time - publish_interval);

        else

            fprintf( ...
                "\n>>> INVALID FAULT ID: %g <<<\n", ...
                requested_fault);

            fprintf( ...
                ">>> Allowed values: 0, 1, 2, 3, 4 <<<\n\n");

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

    rpm = telemetry_log(:, 1);
    fuel_flow = telemetry_log(:, 2);
    torque = telemetry_log(:, 3);
    oil_temperature = telemetry_log(:, 4);
    oil_pressure = telemetry_log(:, 5);
    cht = telemetry_log(:, 6);
    egt = telemetry_log(:, 8);
    vibration = telemetry_log(:, 9);

    %% External input values

    throttle = u(1, 1);
    engine_load = u(1, 2);
    altitude = u(1, 3);
    ambient_temperature = u(1, 4);

    %% Get latest values

    rpm = rpm(end);
    fuel_flow = fuel_flow(end);
    torque = torque(end);
    oil_temperature = oil_temperature(end);
    oil_pressure = oil_pressure(end);
    cht = cht(end);
    egt = egt(end);
    vibration = vibration(end);

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
        '"throttle":%.3f,' ...
        '"engine_load":%.3f,' ...
        '"altitude":%.3f,' ...
        '"ambient_temperature":%.3f}' ...
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
        ambient_temperature);
    %% Publish telemetry

    msg = client.publish( ...
        telemetry_topic, ...
        payload, ...
        int32(1));

    msg.wait_for_publish();

    %% Console output

    fprintf( ...
        "t=%4.0fs | fault=%d | RPM=%7.1f | Torque=%5.2f | CHT=%6.1f | EGT=%7.1f\n", ...
        next_time, ...
        current_fault, ...
        rpm, ...
        torque, ...
        cht, ...
        egt);

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

client.loop_stop();
client.disconnect();

fprintf("\n");
fprintf("========================================\n");
fprintf("LIVE SIMULATION FINISHED\n");
fprintf("========================================\n");
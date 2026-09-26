%% generate_ml_dataset.m

clear;
clc;

%% Model
model_name = 'AeroPistonEngineSimulator';

load_system(model_name);
engine_params;

%% Simulation settings
simulation_time = 100;

% 0.1 second sampling
common_time = (0:0.1:simulation_time)';

%% Fault definitions
% 0 = Healthy
% 1 = Misfire
% 2 = Overheating
% 3 = Oil-pressure failure
% 4 = Fuel starvation

fault_types = [0 1 2 3 4];

% 6 runs per fault
runs_per_fault = 6;

%% Initialize dataset
master_dataset = table();

%% Generate simulations
for fault = fault_types

    for run = 1:runs_per_fault

        fprintf('\n========================================\n');
        fprintf('Fault ID: %d | Run: %d/%d\n', ...
            fault, run, runs_per_fault);
        fprintf('========================================\n');

        %% Random operating conditions

        % Throttle: 60% - 100%
        throttle = 0.60 + (0.40 * rand);

        % Engine load: 30% - 70%
        engine_load = 0.30 + (0.40 * rand);

        % Altitude: 0 - 1000 m
        altitude = 1000 * rand;

        % Ambient temperature: 20 - 35 C
        ambient_temp = 20 + (15 * rand);

        fprintf('Throttle      : %.4f\n', throttle);
        fprintf('Engine Load   : %.4f\n', engine_load);
        fprintf('Altitude      : %.4f m\n', altitude);
        fprintf('Ambient Temp  : %.4f C\n', ambient_temp);

        %% External input

        t = common_time;

        u = [
            throttle * ones(size(t)), ...
            engine_load * ones(size(t)), ...
            altitude * ones(size(t)), ...
            ambient_temp * ones(size(t))
        ];

        %% Set Fault ID

        set_param( ...
            [model_name '/Fault_ID'], ...
            'Value', num2str(fault) ...
        );

        %% Run simulation

        simOut = sim( ...
            model_name, ...
            'StopTime', num2str(simulation_time) ...
        );

        %% Get telemetry

        telemetry_log = simOut.telemetry_log;

        %% Extract telemetry

        time1 = telemetry_log.signal1.Time;
        data1 = squeeze(telemetry_log.signal1.Data);

        time2 = telemetry_log.signal2.Time;
        data2 = squeeze(telemetry_log.signal2.Data);

        time3 = telemetry_log.signal3.Time;
        data3 = squeeze(telemetry_log.signal3.Data);

        time4 = telemetry_log.signal4.Time;
        data4 = squeeze(telemetry_log.signal4.Data);

        time5 = telemetry_log.signal5.Time;
        data5 = squeeze(telemetry_log.signal5.Data);

        time6 = telemetry_log.signal6.Time;
        data6 = squeeze(telemetry_log.signal6.Data);

        time7 = telemetry_log.signal7.Time;
        data7 = squeeze(telemetry_log.signal7.Data);

        time8 = telemetry_log.signal8.Time;
        data8 = squeeze(telemetry_log.signal8.Data);

        time9 = telemetry_log.signal9.Time;
        data9 = squeeze(telemetry_log.signal9.Data);

        %% Resample to common timeline

        RPM = interp1( ...
            time1, data1, common_time, 'linear');

        FuelFlow = interp1( ...
            time2, data2, common_time, 'linear');

        Torque = interp1( ...
            time3, data3, common_time, 'linear');

        OilTemperature = interp1( ...
            time4, data4, common_time, 'linear');

        OilPressure = interp1( ...
            time5, data5, common_time, 'linear');

        CHT = interp1( ...
            time6, data6, common_time, 'linear');

        EGT = interp1( ...
            time8, data8, common_time, 'linear');

        Vibration = interp1( ...
            time9, data9, common_time, 'linear');

        %% Fault ID

        FaultID = repmat( ...
            data7(1), ...
            length(common_time), ...
            1);

        %% Build run table

        run_table = table( ...
            common_time, ...
            RPM, ...
            FuelFlow, ...
            Torque, ...
            OilTemperature, ...
            OilPressure, ...
            CHT, ...
            FaultID, ...
            EGT, ...
            Vibration, ...
            'VariableNames', { ...
                'Time', ...
                'RPM', ...
                'FuelFlow', ...
                'Torque', ...
                'OilTemperature', ...
                'OilPressure', ...
                'CHT', ...
                'FaultID', ...
                'EGT', ...
                'Vibration' ...
            });

        %% Add operating-condition metadata

        run_table.RunID = ...
            repmat( ...
                run + fault * 100, ...
                height(run_table), ...
                1);

        run_table.Throttle = ...
            repmat( ...
                throttle, ...
                height(run_table), ...
                1);

        run_table.EngineLoad = ...
            repmat( ...
                engine_load, ...
                height(run_table), ...
                1);

        run_table.Altitude = ...
            repmat( ...
                altitude, ...
                height(run_table), ...
                1);

        run_table.AmbientTemp = ...
            repmat( ...
                ambient_temp, ...
                height(run_table), ...
                1);

        %% Add to master dataset

        master_dataset = [
            master_dataset;
            run_table
        ];

    end
end

%% Remove invalid rows if any

master_dataset = rmmissing(master_dataset);

%% Round continuous numerical values to 4 decimal places

numeric_vars = {
    'RPM', ...
    'FuelFlow', ...
    'Torque', ...
    'OilTemperature', ...
    'OilPressure', ...
    'CHT', ...
    'EGT', ...
    'Vibration', ...
    'Throttle', ...
    'EngineLoad', ...
    'Altitude', ...
    'AmbientTemp'
};

for i = 1:length(numeric_vars)

    master_dataset.(numeric_vars{i}) = ...
        round(master_dataset.(numeric_vars{i}), 4);

end

%% Save dataset

output_file = 'engine_digital_twin_dataset.csv';

writetable( ...
    master_dataset, ...
    output_file);

%% Final report

fprintf('\n\n========================================\n');
fprintf('DATASET GENERATION COMPLETE\n');
fprintf('========================================\n');

fprintf('Fault classes : %d\n', length(fault_types));
fprintf('Runs/fault    : %d\n', runs_per_fault);
fprintf('Simulation    : %d seconds\n', simulation_time);
fprintf('Sampling      : 0.1 seconds\n');

fprintf('Rows          : %d\n', height(master_dataset));
fprintf('Columns       : %d\n', width(master_dataset));

fprintf('Output file   : %s\n', output_file);

fprintf('========================================\n');

%% Show fault distribution

fprintf('\nFault distribution:\n');

fault_counts = groupcounts( ...
    master_dataset, ...
    'FaultID');

disp(fault_counts);
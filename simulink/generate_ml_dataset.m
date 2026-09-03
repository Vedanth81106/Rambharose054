% generate_ml_dataset.m
model_name = 'AeroPistonEngineTwin';
load_system(model_name);

% Define the scenarios you want to simulate
fault_types = [0, 1, 2, 3]; % 0: Healthy, 1: Misfire, 2: Overheating, 3: Oil Leak
runs_per_fault = 10; % Increase this for your final ML dataset

% Initialize an empty table to hold all data
master_dataset = table();

for fault = fault_types
    for run = 1:runs_per_fault
        disp(['Simulating Fault ID: ', num2str(fault), ' - Run: ', num2str(run)]);

        % 1. Set the fault state in the base workspace
        assignin('base', 'Fault_ID', fault);

        % Optional: Randomize ambient temp or payload slightly per run 
        % to prevent the ML model from memorizing a single perfect flight
        assignin('base', 'AmbientTemp', 25 + (randn * 2)); 

        % 2. Execute the Simulink model programmatically
        % Assuming a 1500 second mission profile
        simOut = sim(model_name, 'StopTime', '1500'); 

        % 3. Extract the timetable from the simulation output
        run_data = simOut.telemetry_log;

        
        % 4. Add a "Run_ID" column to track separate flights
        run_data.Run_ID = repmat(run + (fault * 100), height(run_data), 1);

        % 5. Append to the master dataset
        % Convert timetable to standard table to easily stack them
        run_table = timetable2table(run_data); 
        master_dataset = [master_dataset; run_table];
    end
end

% 6. Export the massive compiled table to a CSV file for Python
writetable(master_dataset, 'engine_digital_twin_dataset.csv');
disp('Dataset generation complete. Saved to engine_digital_twin_dataset.csv');
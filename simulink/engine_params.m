
C_oil = 5000;

%% ========================================================================
%  GLOBAL & ENGINE STRUCTURAL CONSTANTS
%  ========================================================================
T_max        = 10;       % Maximum engine torque (Nm) - 100cc class engine
J_engine     = 0.05;     % Total rotational inertia of crank & prop (kg*m^2)
RPM_idle     = 1500;     % Idle speed (RPM)
RPM_max      = 7500;     % Maximum rated engine speed (RPM)

%% ========================================================================
%  PHASE 2: ENVIRONMENT & ISA CONSTANTS
%  ========================================================================
P0           = 101325;   % Sea-level standard atmospheric pressure (Pa)
T0           = 288.15;   % Sea-level standard temperature (K)
rho0         = 1.225;    % Sea-level standard air density (kg/m^3)
L_lapse      = 0.0065;   % Atmospheric temperature lapse rate (K/m)
R_air        = 287.05;   % Specific gas constant for dry air (J/(kg*K))
g_gravity    = 9.80665;  % Standard gravity acceleration (m/s^2)

%% ========================================================================
%  PHASE 3: FRICTION MODEL CONSTANTS
%  ========================================================================
friction_a   = 0.001;    % Linear friction coefficient (Nm / (rad/s))
friction_b = 0.00005;  % Viscous/quadratic friction coefficient (Nm / (rad/s)^2)

%% ========================================================================
%  PHASE 4: FUEL SYSTEM CONSTANTS
%  ========================================================================
BSFC_nominal = 280;      % Nominal Brake Specific Fuel Consumption (g/kWh)
fuel_min     = 0.2;      % Minimum idle fuel flow limit (kg/hr)

%% ========================================================================
%  PHASES 5 & 6: THERMAL MODEL CONSTANTS (CHT & EGT)
%  ========================================================================
% Cylinder Head Temperature (CHT)
CHT_capacity = 500;      % Cylinder thermal mass/capacity (J/°C)
k_h          = 5000;     % Heat generation scaling factor
k_c          = 0.1;      % Air cooling efficiency scaling factor
CHT_init     = 25;       % Initial engine temperature before start (°C)

% Exhaust Gas Temperature (EGT)
k1_egt       = 150;      % EGT fuel flow sensitivity gain
k2_egt       = 100;      % EGT engine load sensitivity gain
k3_egt       = 0.05;     % EGT RPM sensitivity gain
EGT_tau      = 0.8;      % EGT thermocouple time constant (seconds)

%% ========================================================================
%  PHASE 7: LUBRICATION MODEL CONSTANTS
%  ========================================================================
% Oil Temperature
Oil_capacity = 250;      % Oil thermal mass/capacity (J/°C)
k_oil_heat   = 2.5;      % Mechanical heat dissipation into oil gain
k_oil_cool   = 0.05;     % Oil cooling dissipation gain
OilTemp_init = 25;       % Initial oil temperature before start (°C)

% Oil Pressure
kp_oil       = 0.015;    % Oil pump pressure-to-RPM gain (psi/RPM)
kt_oil       = 0.2;      % Temperature viscosity loss coefficient (psi/°C)
T_oil_ref    = 90;       % Nominal optimal operating oil temperature (°C)

%% ========================================================================
%  PHASE 8: VIBRATION MODEL CONSTANTS
%  ========================================================================
k_vib_amp    = 0.001;    % Baseline vibration amplitude scaling factor
vib_noise_pwr= 0.1;      % High-frequency white noise power for vibration

%% ========================================================================
%  PHASE 9: SENSOR DYNAMICS, NOISE, DRIFT & TELEMETRY SAMPLING
%  ========================================================================
% Sensor Response Time Constants (Transfer Function Tau in seconds)
tau_rpm_sensor      = 0.05;
tau_cht_sensor      = 3.0;
tau_egt_sensor      = 0.8;
tau_fuel_sensor     = 0.2;
tau_oilp_sensor     = 0.1;
tau_oilt_sensor     = 2.0;
tau_vib_sensor      = 0.005;

% Sensor Measurement Noise Variance (Band-Limited White Noise Power)
noise_rpm           = 0.01;
noise_cht           = 0.05;
noise_egt           = 0.2;
noise_fuel          = 0.001;
noise_oilp          = 0.05;
noise_oilt          = 0.02;
noise_vib           = 0.1;

% Sensor Drift Rates (Ramp Slope per second)
drift_cht           = 0.001;   % Thermal drift over flight duration
drift_egt           = 0.002;
drift_oilp          = -0.0005; % Pressure calibration loss

% Sensor Telemetry Sampling Rates (Zero-Order Hold Sample Time in seconds)
Ts_telemetry_std    = 0.1;     % 10 Hz telemetry rate for standard signals
Ts_telemetry_fast   = 0.005;   % 200 Hz sampling rate for high-freq vibration
Ts_telemetry_slow   = 0.5;     % 2 Hz sampling rate for slow thermal channels
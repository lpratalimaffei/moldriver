"""
   Main Driver to parse and sort the mechanism input files and
   launch the desired drivers
"""

import sys
from drivers import esdriver
from drivers import thermodriver
from drivers import ktpdriver
from lib.amech_io import reader
from lib.amech_io import printer
from lib.filesys.build import prefix_fs


# Set runtime options based on user input
JOB_PATH = sys.argv[1]

# Print the header message for the driver
printer.program_header('amech')
printer.random_cute_animal()
printer.program_header('inp')

# Parse the run input
print('\nReading run.dat...')
RUN_INP_DCT = reader.run.build_run_inp_dct(JOB_PATH)
RUN_OBJ_DCT = reader.run.objects_dct(JOB_PATH)
RUN_JOBS_LST = reader.run.build_run_jobs_lst(JOB_PATH)
ES_TSK_STR = reader.run.read_es_tsks(JOB_PATH)

# Parse the theory input
print('\nReading theory.dat...')
THY_DCT = reader.theory.build_thy_dct(JOB_PATH)

# Parse the model input
print('\nReading model.dat...')
PES_MODEL_DCT, SPC_MODEL_DCT = reader.model.read_models_sections(JOB_PATH)

# Parse the species input to get a dct with ALL species in mechanism
print('\nReading species.csv...')
SPC_DCT = reader.species.build_spc_dct(JOB_PATH, 'csv', check_stereo=False)

# Parse mechanism input and get a dct with info on PESs user request to run
if RUN_OBJ_DCT['pes']:
    print('\nRunning Calculations for PESs. Need input for mechanism.')
    CLA_DCT = reader.rclass.parse_rxn_class_file(JOB_PATH)
    print('  Reading mechanism.dat...')
    RUN_PES_DCT = reader.mechanism.parse_mechanism_file(
        JOB_PATH,
        RUN_INP_DCT['mech'],
        SPC_DCT,
        RUN_OBJ_DCT['pes'],
        sort_rxns=True
    )
elif RUN_OBJ_DCT['spc']:
    RUN_PES_DCT = {}
    RUN_SPC_LST_DCT = reader.species.build_run_spc_dct(SPC_DCT, RUN_OBJ_DCT)
    CLA_DCT = {}
else:
    print('No Proper Run object specified')
    sys.exit()

# Initialize the filesystem
print('\nBuilding the base Run-Save filesystems at')
prefix_fs(RUN_INP_DCT['run_prefix'])
print('{}'.format(RUN_INP_DCT['run_prefix']))
prefix_fs(RUN_INP_DCT['save_prefix'])
print('{}'.format(RUN_INP_DCT['save_prefix']))

# Run the requested drivers: es, thermo, ktp
print('\n\nRunning the requested drivers...')
if 'es' in RUN_JOBS_LST:

    printer.program_header('es')

    # Build the elec struct tsk lst
    ES_TSK_LST = reader.run.build_run_es_tsks_lst(
        ES_TSK_STR, SPC_MODEL_DCT, THY_DCT)

    # Call ESDriver for spc in each PES or SPC
    if RUN_OBJ_DCT['pes']:
        for (formula, pes_idx, sub_pes_idx), rxn_lst in RUN_PES_DCT.items():

            # Print PES form and SUB PES Channels
            print('\nRunning PES {}: {}, SUB PES {}'.format(
                pes_idx, formula, sub_pes_idx))
            for chn_idx, rxn in enumerate(rxn_lst):
                print('  Running Channel {} for {} = {}'.format(
                    chn_idx+1,
                    '+'.join(rxn['reacs']),
                    '+'.join(rxn['prods'])))

            esdriver.run(
                pes_idx,
                rxn_lst,
                SPC_DCT,
                CLA_DCT,
                ES_TSK_LST,
                THY_DCT,
                RUN_INP_DCT
            )
    else:
        PES_IDX = 0
        esdriver.run(
            PES_IDX,
            RUN_SPC_LST_DCT,
            SPC_DCT,
            CLA_DCT,
            ES_TSK_LST,
            THY_DCT,
            RUN_INP_DCT
        )

WRITE_MESSPF, RUN_MESSPF, RUN_NASA = reader.run.set_thermodriver(RUN_JOBS_LST)
if WRITE_MESSPF or RUN_MESSPF or RUN_NASA:

    printer.program_header('thermo')

    # Call ThermoDriver for spc in PES
    if RUN_OBJ_DCT['pes']:
        for _, rxn_lst in RUN_PES_DCT.items():
            thermodriver.run(
                SPC_DCT,
                PES_MODEL_DCT, SPC_MODEL_DCT,
                THY_DCT,
                rxn_lst,
                RUN_INP_DCT,
                write_messpf=WRITE_MESSPF,
                run_messpf=RUN_MESSPF,
                run_nasa=RUN_NASA,
            )
    else:
        thermodriver.run(
            SPC_DCT,
            PES_MODEL_DCT, SPC_MODEL_DCT,
            THY_DCT,
            RUN_SPC_LST_DCT,
            RUN_INP_DCT,
            write_messpf=WRITE_MESSPF,
            run_messpf=RUN_MESSPF,
            run_nasa=RUN_NASA,
        )

WRITE_MESSRATE, RUN_MESSRATE, RUN_FITS = reader.run.set_ktpdriver(RUN_JOBS_LST)
if WRITE_MESSRATE or RUN_MESSRATE or RUN_FITS:

    printer.program_header('ktp')

    # Call kTPDriver for each SUB PES
    if RUN_OBJ_DCT['pes']:
        for (formula, pes_idx, sub_pes_idx), rxn_lst in RUN_PES_DCT.items():

            # Print PES form and SUB PES Channels
            print('\nCalculating Rates for PES {}: {}, SUB PES {}'.format(
                pes_idx, formula, sub_pes_idx))
            for chn_idx, rxn in enumerate(rxn_lst):
                print('  Including Channel {}: {} = {}'.format(
                    chn_idx+1,
                    '+'.join(rxn['reacs']),
                    '+'.join(rxn['prods'])))

            ktpdriver.run(
                formula, pes_idx, sub_pes_idx,
                SPC_DCT,
                CLA_DCT,
                THY_DCT,
                rxn_lst,
                PES_MODEL_DCT, SPC_MODEL_DCT,
                RUN_INP_DCT,
                write_messrate=WRITE_MESSRATE,
                run_messrate=RUN_MESSRATE,
                run_fits=RUN_FITS
            )
    else:
        print("Can't run kTPDriver without a PES being specified")

print('\n\nAutoMech has completed.')

""" calculates certain quantities of interest using MESS+filesytem
"""

import os
import automol
import autofile
from phydat import phycon
from mechanalyzer.inf import rxn as rinfo
from mechanalyzer.inf import spc as sinfo
from mechanalyzer.inf import thy as tinfo
from mechroutines.pf import thermo as thmroutines
from mechroutines.pf.models import typ
from mechroutines.pf.models import _vib as vib
from mechlib.amech_io import printer as ioprinter


# Functions to hand reading and formatting energies of single species
def read_energy(spc_dct_i, pf_filesystems,
                spc_model_dct_i, run_prefix,
                read_ene=True, read_zpe=True, conf=None, saddle=False):
    """ Get the energy for a species on a channel
    """

    # Read the electronic energy and ZPVE
    e_elec = None
    if read_ene:
        e_elec = electronic_energy(
            spc_dct_i, pf_filesystems, spc_model_dct_i, conf=conf)
        ioprinter.debug_message('e_elec in models ene ', e_elec)

    e_zpe = None
    if read_zpe:
        e_zpe = zero_point_energy(
            spc_dct_i, pf_filesystems, spc_model_dct_i,
            run_prefix, saddle=saddle, conf=conf)
        ioprinter.debug_message('zpe in models ene ', e_zpe)

    # Return the total energy requested
    ene = None
    if read_ene and read_zpe:
        if e_elec is not None and e_zpe is not None:
            ene = e_elec + e_zpe
    elif read_ene and not read_zpe:
        ene = e_elec
    elif read_ene and not read_zpe:
        ene = e_zpe

    return ene


def electronic_energy(spc_dct_i, pf_filesystems, spc_model_dct_i, conf=None):
    """ get high level energy at low level optimized geometry
    """

    ioprinter.info_message('- Calculating electronic energy')

    # spc_dct_i = spc_dct[spc_name]
    rxn_info = spc_dct_i.get('rxn_info', None)
    if rxn_info is not None:
        spc_info = rinfo.ts_info(rxn_info)
    else:
        spc_info = sinfo.from_dct(spc_dct_i)

    # Get the harmonic filesys information
    if conf:
        cnf_path = conf[1]
    else:
        [_, cnf_path, _, _, _] = pf_filesystems['harm']

    # Get the electronic energy levels
    ene_levels = tuple(val[1] for key, val in spc_model_dct_i['ene'].items()
                       if 'lvl' in key)
    print('ene levels', ene_levels)

    # Read the energies from the filesystem
    e_elec = None
    if os.path.exists(cnf_path):

        e_elec = 0.0
        # ioprinter.info_message('lvls', ene_levels)
        for (coeff, level) in ene_levels:
            # Build SP filesys
            mod_thy_info = tinfo.modify_orb_label(level, spc_info)
            sp_save_fs = autofile.fs.single_point(cnf_path)
            sp_save_fs[-1].create(mod_thy_info[1:4])
            # Read the energy
            sp_path = sp_save_fs[-1].path(mod_thy_info[1:4])
            if os.path.exists(sp_path):
                ioprinter.reading('Energy', sp_path)
                ene = sp_save_fs[-1].file.energy.read(mod_thy_info[1:4])
                e_elec += (coeff * ene)
            else:
                ioprinter.warning_message('No energy at path')
                e_elec = None
                break
    else:
        ioprinter.warning_message('No conformer to calculate the energy')

    return e_elec


def zero_point_energy(spc_dct_i,
                      pf_filesystems, spc_model_dct_i,
                      run_prefix, saddle=False, conf=None):
    """ compute the ZPE including torsional and anharmonic corrections
    """

    ioprinter.info_message('- Calculating zero-point energy')

    # Calculate ZPVE
    is_atom = False
    if not saddle:
        if typ.is_atom(spc_dct_i):
            is_atom = True
    if is_atom:
        zpe = 0.0
    else:
        _, _, zpe, _ = vib.vib_analysis(
            spc_dct_i, pf_filesystems, spc_model_dct_i,
            run_prefix, zrxn=(None if not saddle else 'placeholder'))

    return zpe


def rpath_ref_idx(ts_dct, scn_vals, coord_name, scn_prefix,
                  ene_info1, ene_info2):
    """ Get the reference energy along a reaction path
    """

    # Set up the filesystem
    zma_fs = autofile.fs.zmatrix(scn_prefix)
    zma_path = zma_fs[-1].path([0])
    scn_fs = autofile.fs.scan(zma_path)

    ene_info1 = ene_info1[1][0][1]
    ene_info2 = ene_info2[0]
    ioprinter.debug_message('mod_eneinf1', ene_info1)
    ioprinter.debug_message('mod_eneinf2', ene_info2)
    mod_ene_info1 = tinfo.modify_orb_label(
        sinfo.from_dct(ts_dct), ene_info1)
    mod_ene_info2 = tinfo.modify_orb_label(
        sinfo.from_dct(ts_dct), ene_info2)

    ene1, ene2, ref_val = None, None, None
    for val in reversed(scn_vals):
        locs = [[coord_name], [val]]
        path = scn_fs[-1].path(locs)
        hs_fs = autofile.fs.high_spin(path)
        if hs_fs[-1].file.energy.exists(mod_ene_info1[1:4]):
            ene1 = hs_fs[-1].file.energy.read(mod_ene_info1[1:4])
        if hs_fs[-1].file.energy.exists(mod_ene_info2[1:4]):
            ene2 = hs_fs[-1].file.energy.read(mod_ene_info2[1:4])
        if ene1 is not None and ene2 is not None:
            ref_val = val
            break

    if ref_val is not None:
        scn_idx = scn_vals.index(ref_val)

    return scn_idx, ene1, ene2


# Functions to handle energies for a channel
def set_reference_ene(rxn_lst, spc_dct, thy_dct,
                      pes_model_dct_i, spc_model_dct_i,
                      run_prefix, save_prefix, ref_idx=0):
    """ Sets the reference species for the PES for which all energies
        are scaled relative to.
    """

    # Set the index for the reference species, right now defualt to 1st spc
    ref_rxn = rxn_lst[ref_idx]

    _, (ref_rgts, _) = ref_rxn

    ioprinter.info_message(
        'Determining the reference energy for PES...', newline=1)
    ioprinter.info_message(
        ' - Reference species assumed to be the',
        ' first set of reactants on PES: {}'.format('+'.join(ref_rgts)))

    # Get the model for the first reference species
    ref_scheme = pes_model_dct_i['therm_fit']['ref_scheme']
    ref_enes = pes_model_dct_i['therm_fit']['ref_enes']

    ref_ene_level = spc_model_dct_i['ene']['lvl1'][0]
    ioprinter.info_message(
        ' - Energy Level for Reference Species: {}'.format(ref_ene_level))

    # Get the elec+zpe energy for the reference species
    ioprinter.info_message('')
    hf0k = 0.0
    for rgt in ref_rgts:

        ioprinter.info_message(' - Calculating energy for {}...'.format(rgt))
        basis_dct, uniref_dct = thmroutines.basis.prepare_refs(
            ref_scheme, spc_dct, [[rgt, None]], run_prefix, save_prefix)
        spc_basis, coeff_basis = basis_dct[rgt]

        # Build filesystem
        ene_spc, ene_basis = thmroutines.basis.basis_energy(
            rgt, spc_basis, uniref_dct, spc_dct,
            spc_model_dct_i, run_prefix, save_prefix)

        # Calcualte the total energy
        hf0k += thmroutines.heatform.calc_hform_0k(
            ene_spc, ene_basis, spc_basis, coeff_basis, ref_set=ref_enes)

    hf0k *= phycon.KCAL2EH

    return hf0k


def calc_channel_enes(chnl_infs, ref_ene,
                      chn_model, first_ground_model):
    """ Get the energies for several points on the reaction channel.
        The energy is determined by two different methods:
            (1) Read from the file system if chn_model == first_ground_model
            (2) Shift ene for the channel if chn_model != first_ground_model
    """

    if chn_model == first_ground_model:
        chn_enes = sum_channel_enes(chnl_infs, ref_ene, ene_lvl='ene_chnlvl')
    else:
        chn_enes1 = sum_channel_enes(chnl_infs, ref_ene, ene_lvl='ene_reflvl')
        chn_enes2 = sum_channel_enes(chnl_infs, ref_ene, ene_lvl='ene_reflvl')
        chn_enes = shift_enes(chn_enes1, chn_enes2)

    return chn_enes


def sum_channel_enes(channel_infs, ref_ene, ene_lvl='ene_chnlvl'):
    """ sum the energies
    """

    # Initialize sum ene dct
    sum_ene = {}

    # Calculate energies for species
    reac_ene = 0.0
    reac_ref_ene = 0.0
    for rct in channel_infs['reacs']:
        reac_ene += rct[ene_lvl]
        reac_ref_ene += rct['ene_tsref']
        ioprinter.info_message('reac ene', rct[ene_lvl], rct['ene_tsref'])
    sum_ene.update({'reacs': reac_ene})

    prod_ene = 0.0
    prod_ref_ene = 0.0
    for prd in channel_infs['prods']:
        prod_ene += prd[ene_lvl]
        prod_ref_ene += prd['ene_tsref']
        ioprinter.info_message('prod ene', prd[ene_lvl], prd['ene_tsref'])
    sum_ene.update({'prods': prod_ene})

    # Calculate energies for fake entrance- and exit-channel wells
    if 'fake_vdwr' in channel_infs:
        vdwr_ene = reac_ene - (1.0 * phycon.KCAL2EH)
        sum_ene.update(
            {'fake_vdwr': vdwr_ene, 'fake_vdwr_ts': reac_ene}
        )
    if 'fake_vdwp' in channel_infs:
        vdwp_ene = prod_ene - (1.0 * phycon.KCAL2EH)
        sum_ene.update(
            {'fake_vdwp': vdwp_ene, 'fake_vdwp_ts': prod_ene}
        )

    ioprinter.debug_message(
        'REAC HoF (0 K) spc lvl kcal/mol: ', reac_ene * phycon.EH2KCAL)
    ioprinter.debug_message(
        'REAC HoF (0 K) ts lvl kcal/mol: ', reac_ref_ene * phycon.EH2KCAL)
    ioprinter.debug_message(
        'PROD HoF (0 K) spc lvl kcal/mol: ', prod_ene * phycon.EH2KCAL)
    ioprinter.debug_message(
        'PROD HoF (0 K) ts lvl kcal/mol: ', prod_ref_ene * phycon.EH2KCAL)
    # Scale all of the current energies in the dict
    for spc, ene in sum_ene.items():
        sum_ene[spc] = (ene - ref_ene) * phycon.EH2KCAL

# Set the inner TS ene and scale them

    if channel_infs['ts'][0]['writer'] in ('pst_block', 'vrctst_block'):
        if len(channel_infs['reacs']) == 2:
            ts_enes = [sum(inf['ene_chnlvl'] for inf in channel_infs['reacs'])]
        else:
            ts_enes = [sum(inf['ene_chnlvl'] for inf in channel_infs['prods'])]
        channel_infs['ts'][0].update({'ene_chnlvl': ts_enes})
    else:
        if 'rpath' in channel_infs['ts']:
            ts_enes = [dct[ene_lvl] for dct in channel_infs['ts']['rpath']]
        else:
            ts_enes = [dct[ene_lvl] for dct in channel_infs['ts']]
            # ts_enes = [channel_infs['ts'][ene_lvl]]
        ioprinter.debug_message(
            'TS HoF (0 K) ts lvl kcal/mol: ', ts_enes[0] * phycon.EH2KCAL)
        if reac_ref_ene:
            if abs(ts_enes[0] - reac_ref_ene) < abs(ts_enes[0] - prod_ref_ene):
                ts_enes = [ene - reac_ref_ene + reac_ene for ene in ts_enes]
            else:
                ts_enes = [ene - prod_ref_ene + prod_ene for ene in ts_enes]
        ioprinter.debug_message(
            'TS HoF (0 K) approx spc lvl kcal/mol: ',
            ts_enes[0] * phycon.EH2KCAL)
    ts_enes = [(ene - ref_ene) * phycon.EH2KCAL for ene in ts_enes]

    sum_ene.update({'ts': ts_enes})

    return sum_ene


def shift_enes(chn_enes1, chn_enes2):
    """ When two channels dont match, the energies need to be shifted
        to bring them into alignment.
    """

    # Find a species that has enes with both methods to be used to scale
    # I don't think we need to use any species, so I will use the first
    for spc in chn_enes1:
        if chn_enes1[spc] is not None and chn_enes2[spc] is not None:
            scale_ref_spcs = spc
            break
    scale_ref_ene1 = chn_enes1[scale_ref_spcs]
    scale_ref_ene2 = chn_enes2[scale_ref_spcs]

    # Now return a dct with the lvl1 enes or the scaled lvl2 enes
    fin_enes = {}
    for spc in chn_enes1:
        if chn_enes1[spc] is not None:
            fin_enes[spc] = chn_enes1[spc]
        else:
            fin_enes[spc] = scale_ref_ene1 + (chn_enes2[spc] - scale_ref_ene2)

    return fin_enes


# Writer
def zpe_str(spc_dct, zpe):
    """ return the zpe for a given species according a specified set of
    partition function levels
    """
    if automol.geom.is_atom(automol.inchi.geometry(spc_dct['inchi'])):
        zero_energy_str = 'End'
    else:
        zero_energy_str = ' ZeroEnergy[kcal/mol] ' + str(zpe)
        zero_energy_str += '\nEnd'

    return zero_energy_str

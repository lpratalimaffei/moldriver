"""
  CHEMKIN for ETRANS
"""

import automol
import autofile
import chemkin_io.writer
from mechlib import filesys
from mechlib.amech_io import printer as ioprinter


def build_transport_file(tgt_queue,
                         spc_dct, thy_dct, etrans_keyword_dct,
                         save_prefix):
    """ Write the chemkin string
    """

    bath_name = etrans_keyword_dct['bath']

    # Get the base theory info obj
    thy_info = filesys.inf.get_es_info(
        etrans_keyword_dct['runlvl'], thy_dct)

    # Read the epsilon and sigma params for the BATH+BATH interaction
    cnf_save_fs, min_cnf_locs, etrans_fs, etrans_locs = _etrans_fs(
        spc_dct, bath_name, bath_name, thy_info, save_prefix)
    if etrans_fs[-1].file.epsilon.exists(etrans_locs):
        bb_eps = etrans_fs[-1].file.epsilon.read(etrans_locs)
    else:
        bb_eps = None
    if etrans_fs[-1].file.sigma.exists(etrans_locs):
        bb_sig = etrans_fs[-1].file.sigma.read(etrans_locs)
    else:
        bb_sig = None

    # Now obtain all the properties for the TGT+TGT interaction for CKIN
    # Uses simple combining rules for the LJ params
    trans_dct = {}
    for tgt_name, _ in tgt_queue:

        # Build the filesystem objects needed for the TGT+BATH interaction
        cnf_save_fs, min_cnf_locs, etrans_fs, etrans_locs = _etrans_fs(
            spc_dct, tgt_name, bath_name, thy_info, save_prefix)

        # Read the conformer filesystems
        if cnf_save_fs[-1].file.geometry.exists(min_cnf_locs):
            geo = cnf_save_fs[-1].file.geometry.read(min_cnf_locs)
        else:
            geo = None
        if cnf_save_fs[-1].file.dipole_moment.exists(min_cnf_locs):
            vec = cnf_save_fs[-1].file.dipole_moment.read(min_cnf_locs)
            dip_mom = automol.prop.total_dipole_moment(vec)
        else:
            dip_mom = None
        if cnf_save_fs[-1].file.polarizability.exists(min_cnf_locs):
            tensor = cnf_save_fs[-1].file.polarizability.read(min_cnf_locs)
            polar = automol.prop.total_polarizability(tensor)
        else:
            polar = None

        # Read the energy transfer filesystems
        if etrans_fs[-1].file.epsilon.exists(etrans_locs):
            tb_eps = etrans_fs[-1].file.epsilon.read(etrans_locs)
        else:
            tb_eps = None
        if etrans_fs[-1].file.sigma.exists(etrans_locs):
            tb_sig = etrans_fs[-1].file.sigma.read(etrans_locs)
        else:
            tb_sig = None

        # Use combine rules for the sigma and epsilon
        tt_eps = automol.etrans.combine.epsilon(tb_eps, bb_eps)
        tt_sig = automol.etrans.combine.sigma(tb_sig, bb_sig)

        # Build dct and append it ot overall dictionary Append info to list
        dct = {
            'geo': geo,
            'dipole_moment': dip_mom,
            'polarizability': polar,
            'epsilon': tt_eps,
            'sigma': tt_sig
        }
        trans_dct.update({tgt_name: dct})

    # Write the string with all of the transport properties
    transport_str = chemkin_io.writer.transport.properties(trans_dct)
    ioprinter.debug_message('transport_str\n', transport_str, newline=1)
    ioprinter.obj('vspace')
    ioprinter.obj('line_dash')
    ioprinter.info_message('Writing the CHEMKIN transport file', newline=1)

    return transport_str


def _etrans_fs(spc_dct, tgt_name, bath_name, thy_info, save_prefix):
    """ Build the energy transfer filesys
    """

    # Get the info for the target combined spc info objects
    tgt_dct = spc_dct[tgt_name]
    bath_dct = spc_dct[bath_name]
    tgt_info = filesys.inf.get_spc_info(tgt_dct)
    bath_info = filesys.inf.get_spc_info(bath_dct)
    lj_info = filesys.inf.combine_spc_info(tgt_info, bath_info)

    # Build the modified thy objs
    mod_tgt_thy_info = filesys.inf.modify_orb_restrict(tgt_info, thy_info)
    mod_lj_thy_info = filesys.inf.modify_orb_restrict(lj_info, thy_info)

    # Build the conformer filesystem objects
    _, thy_save_path = filesys.build.spc_thy_fs_from_root(
        save_prefix, tgt_info, mod_tgt_thy_info)

    cnf_save_fs = autofile.fs.conformer(thy_save_path)
    cnf_rng_info = filesys.mincnf.min_energy_conformer_locators(
        cnf_save_fs, mod_tgt_thy_info)
    min_cnf_locs, min_cnf_path = cnf_rng_info

    # Build the energy transfer filesystem objects
    etrans_fs, etrans_locs = filesys.build.etrans_fs_from_prefix(
        min_cnf_path, bath_info, mod_lj_thy_info)

    return cnf_save_fs, min_cnf_locs, etrans_fs, etrans_locs

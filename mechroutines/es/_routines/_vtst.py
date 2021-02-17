""" Run and Read the scans from VTST calculations
"""

import automol
import autofile
from mechroutines.es._routines import sp
from mechroutines.es._routines import _wfn as wfn
from mechroutines.es.runner import scan
from mechlib import filesys
from mechlib.submission import qchem_params
from mechlib.reaction import grid as rxngrid
from mechlib.amech_io import printer as ioprinter


def radrad_scan(ts_zma, ts_info, hs_info,
                ts_formula, high_mul, active_space,
                rct_info, rct_ichs, rcts_cnf_fs, rcts_gra,
                grid1, grid2, coord_name, frm_bnd_keys,
                mod_var_scn_thy_info,
                mod_var_sp1_thy_info,  # Need an unmodifie
                var_sp1_thy_info,
                var_sp2_thy_info,
                hs_var_sp1_thy_info,
                hs_var_sp2_thy_info,
                mod_thy_info,
                vscnlvl_thy_save_fs,
                vscnlvl_ts_save_fs,
                scn_run_fs, scn_save_fs,
                pot_thresh,
                overwrite, update_guess,
                constraint_dct=None,
                zma_locs=(0,)):
    """ Run the scan for VTST calculations
    """

    # Set up the casscf options
    ref_zma = automol.zmat.set_values_by_name(ts_zma, {coord_name: grid1[0]})
    cas_kwargs = wfn.build_wfn(ref_zma, ts_info, ts_formula, high_mul,
                               rct_ichs, rct_info,
                               active_space, mod_var_scn_thy_info)

    # Run the scan along the reaction coordinate
    scan.multiref_rscan(
        ts_zma=ts_zma,
        ts_info=ts_info,
        grid1=grid1,
        grid2=grid2,
        coord_name=coord_name,
        mod_var_scn_thy_info=mod_var_scn_thy_info,
        vscnlvl_thy_save_fs=vscnlvl_thy_save_fs,
        scn_run_fs=scn_run_fs,
        scn_save_fs=scn_save_fs,
        overwrite=overwrite,
        update_guess=update_guess,
        constraint_dct=constraint_dct,
        **cas_kwargs
    )

    # Assess the potentials to see if there is a saddle point zma
    ioprinter.debug_message('above vtst max')
    sadpt_zma = rxngrid.vtst_max(
        list(grid1)+list(grid2), coord_name, scn_save_fs,
        mod_var_scn_thy_info, constraint_dct,
        ethresh=pot_thresh)

    ioprinter.debug_message('sadpt_zma', sadpt_zma)
    if sadpt_zma is None:
        # Calculate and the energies needed for inf sep ene
        far_locs = [[coord_name], [grid1[0]]]
        ts_zma = scn_save_fs[-1].file.zmatrix.read(far_locs)
        geo = scn_save_fs[-1].file.geometry.read(far_locs)

        geo_run_path = scn_run_fs[-1].path(far_locs)
        geo_save_path = scn_save_fs[-1].path(far_locs)

        _ = scan.radrad_inf_sep_ene(
            hs_info, ts_zma,
            rct_info, rcts_cnf_fs,
            var_sp1_thy_info, var_sp2_thy_info,
            hs_var_sp1_thy_info, hs_var_sp2_thy_info,
            geo, geo_run_path, geo_save_path,
            scn_save_fs, far_locs,
            overwrite=overwrite,
            **cas_kwargs)

        # Save the vmatrix for use in reading
        _save_traj(ts_zma, frm_bnd_keys, rcts_gra,
                   vscnlvl_ts_save_fs, zma_locs=zma_locs)

        ioprinter.info_message(
            'Running Hessians and energies...', newline=1)
        _vtst_hess_ene(ts_info, coord_name,
                       mod_var_scn_thy_info, mod_var_sp1_thy_info,
                       scn_save_fs, scn_run_fs,
                       overwrite, **cas_kwargs)


def molrad_scan(ts_zma, ts_info,
                rct_info, rcts_cnf_fs, rcts_gra,
                grid1, grid2, coord_name, frm_bnd_keys,
                thy_info, vsp1_thy_info,
                thy_save_fs,
                ts_save_fs,
                scn_run_fs, scn_save_fs,
                overwrite, update_guess, retryfail,
                zma_locs=(0,)):
    """ Run the scan for VTST calculations
    """

    # Set the thy info objects appropriately
    if vsp1_thy_info is not None:
        inf_thy_info = vsp1_thy_info
    else:
        inf_thy_info = thy_info
    mod_thy_info = filesys.inf.modify_orb_restrict(ts_info, thy_info)
    mod_vsp1_thy_info = filesys.inf.modify_orb_restrict(ts_info, vsp1_thy_info)

    # Set script
    _, opt_script_str, _, opt_kwargs = qchem_params(
        *mod_thy_info[0:2])

    # Setup and run the first part of the scan to shorte
    scan.run_two_way_scan(
        ts_zma, ts_info, mod_thy_info,
        grid1, grid2, coord_name,
        thy_save_fs,
        scn_run_fs, scn_save_fs,
        opt_script_str, overwrite,
        update_guess=update_guess,
        reverse_sweep=False,
        saddle=False,   # opts along scan are min, not sadpt opts
        constraint_dct=None,
        retryfail=retryfail,
        **opt_kwargs
    )

    # Infinite seperation energy calculation
    ioprinter.info_message(
        'Calculating infinite separation energy...', newline=1)
    ioprinter.debug_message('inf_thy_info', inf_thy_info)
    _ = scan.molrad_inf_sep_ene(
        rct_info, rcts_cnf_fs,
        inf_thy_info, overwrite)

    # Save the vmatrix for use in reading
    _save_traj(ts_zma, frm_bnd_keys, rcts_gra,
               ts_save_fs, zma_locs=zma_locs)

    ioprinter.running('Hessians and energies...', newline=1)
    _vtst_hess_ene(ts_info, coord_name,
                   mod_thy_info, mod_vsp1_thy_info,
                   scn_save_fs, scn_run_fs,
                   overwrite, **{})


def _vtst_hess_ene(ts_info, coord_name,
                   mod_thy_info, mod_vsp1_thy_info,
                   scn_save_fs, scn_run_fs,
                   overwrite, **cas_kwargs):
    """ VTST Hessians and Energies
    """

    scn_locs = scn_save_fs[-1].existing([coord_name])

    ioprinter.running('Hessians and Gradients...', newline=1)
    hess_script_str, _, hess_kwargs, _ = qchem_params(
        *mod_thy_info[0:2])
    hess_kwargs.update(cas_kwargs)
    for locs in scn_locs:
        geo_run_path = scn_run_fs[-1].path(locs)
        geo_save_path = scn_save_fs[-1].path(locs)
        scn_run_fs[-1].create(locs)
        zma, geo = filesys.inf.cnf_fs_zma_geo(scn_save_fs, locs)
        sp.run_hessian(zma, geo, ts_info, mod_thy_info,
                       scn_save_fs, geo_run_path, geo_save_path, locs,
                       hess_script_str, overwrite, **hess_kwargs)
        sp.run_gradient(zma, geo, ts_info, mod_thy_info,
                        scn_save_fs, geo_run_path, geo_save_path, locs,
                        hess_script_str, overwrite, **hess_kwargs)

    ioprinter.running('Energies...', newline=1)
    script_str, _, ene_kwargs, _ = qchem_params(
        *mod_vsp1_thy_info[0:2])
    ene_kwargs.update(cas_kwargs)
    for locs in scn_locs:
        geo_run_path = scn_run_fs[-1].path(locs)
        geo_save_path = scn_save_fs[-1].path(locs)
        scn_run_fs[-1].create(locs)
        zma, geo = filesys.inf.cnf_fs_zma_geo(scn_save_fs, locs)
        sp.run_energy(zma, geo, ts_info, mod_vsp1_thy_info,
                      scn_save_fs, geo_run_path, geo_save_path, locs,
                      script_str, overwrite, **ene_kwargs)


def _save_traj(ts_zma, frm_bnd_keys, rcts_gra, ts_save_fs, zma_locs=(0,)):
    """ save trajectory and zma stuff
    """

    ioprinter.info_message(
        'Saving the V-Matrix into the filesystem...', newline=1)
    ts_fs, _ = ts_save_fs
    ts_path = ts_fs[-1].path()
    zma_fs = autofile.fs.zmatrix(ts_path)
    zma_fs[-1].create(zma_locs)
    zma_fs[-1].file.vmatrix.write(automol.zmat.var_(ts_zma), zma_locs)

    ioprinter.info_message(
        'Saving the trajectory into the filesystem...', newline=1)
    tra = (frozenset({frm_bnd_keys}),
           frozenset({}))
    zma_fs[-1].file.transformation.write(tra, zma_locs)
    zma_fs[-1].file.reactant_graph.write(rcts_gra, zma_locs)
"""
  Handle labels
"""

from mechlib.amech_io import printer as ioprinter
from mechroutines.models.typ import need_fake_wells


def make_pes_label_dct(rxn_lst, pes_idx, spc_dct, spc_mod_dct_i):
    """  Loop over all of the reaction channels of the PES to build a
         dictionary that systematically maps the mechanism names of all
         species and transition states to formatted labels used to designate
         each as a well, bimol, or barrier component in a MESS input file.
    """

    pes_label_dct = {}
    for rxn in rxn_lst:
        # Get the wells models
        rwell_mod = spc_mod_dct_i['ts']['rwells']
        pwell_mod = spc_mod_dct_i['ts']['pwells']

        # Get thhe name and class
        chnl_idx, (reacs, prods) = rxn
        tsname = 'ts_{:g}_{:g}'.format(pes_idx+1, chnl_idx+1)
        sub_tsname = '{}_{:g}'.format(tsname, 0)
        rclass = spc_dct[sub_tsname]['class']

        # Build labels
        pes_label_dct.update(
            _make_channel_label_dct(
                tsname, rclass, pes_label_dct, chnl_idx, reacs, prods,
                rwell_mod, pwell_mod))
        ioprinter.debug_message('pes_label dct', pes_label_dct)

    return pes_label_dct


def _make_channel_label_dct(tsname, rclass, label_dct, chn_idx, reacs, prods,
                            rwell_mod, pwell_mod):
    """ Builds a dictionary that matches the mechanism name to the labels used
        in the MESS input and output files.
    """

    # Initialize idxs for bimol, well, and fake species
    pidx, widx, fidx = 1, 1, 1
    for val in label_dct.values():
        if 'P' in val:
            pidx += 1
        elif 'W' in val:
            widx += 1
        elif 'F' in val:
            fidx += 1

    # Determine the idxs for the channel reactants
    reac_label = ''
    bimol = bool(len(reacs) > 1)
    well_dct_key1 = '+'.join(reacs)
    well_dct_key2 = '+'.join(reacs[::-1])
    if well_dct_key1 not in label_dct:
        if well_dct_key2 in label_dct:
            well_dct_key1 = well_dct_key2
        else:
            if bimol:
                reac_label = 'P' + str(pidx)
                pidx += 1
                label_dct[well_dct_key1] = reac_label
            else:
                reac_label = 'W' + str(widx)
                widx += 1
                label_dct[well_dct_key1] = reac_label
    if not reac_label:
        reac_label = label_dct[well_dct_key1]

    # Determine the idxs for the channel products
    prod_label = ''
    bimol = bool(len(prods) > 1)
    well_dct_key1 = '+'.join(prods)
    well_dct_key2 = '+'.join(prods[::-1])
    if well_dct_key1 not in label_dct:
        if well_dct_key2 in label_dct:
            well_dct_key1 = well_dct_key2
        else:
            if bimol:
                prod_label = 'P' + str(pidx)
                label_dct[well_dct_key1] = prod_label
            else:
                prod_label = 'W' + str(widx)
                label_dct[well_dct_key1] = prod_label
    if not prod_label:
        prod_label = label_dct[well_dct_key1]

    # Determine idxs for any fake wells if they are needed
    fake_wellr_label = ''
    if need_fake_wells(rclass, rwell_mod):
        well_dct_key1 = 'F' + '+'.join(reacs)
        well_dct_key2 = 'F' + '+'.join(reacs[::-1])
        if well_dct_key1 not in label_dct:
            if well_dct_key2 in label_dct:
                well_dct_key1 = well_dct_key2
            else:
                fake_wellr_label = 'F' + str(fidx)
                fidx += 1
                label_dct[well_dct_key1] = fake_wellr_label

                pst_r_label = 'FRB' + str(chn_idx)
                label_dct[well_dct_key1.replace('F', 'FRB')] = pst_r_label
            if not fake_wellr_label:
                fake_wellr_label = label_dct[well_dct_key1]
                pst_r_label = label_dct[well_dct_key1.replace('F', 'FRB')]
        else:
            fake_wellr_label = label_dct[well_dct_key1]

    fake_wellp_label = ''
    if need_fake_wells(rclass, pwell_mod):
        well_dct_key1 = 'F' + '+'.join(prods)
        well_dct_key2 = 'F' + '+'.join(prods[::-1])
        if well_dct_key1 not in label_dct:
            if well_dct_key2 in label_dct:
                well_dct_key1 = well_dct_key2
            else:
                fake_wellp_label = 'F' + str(fidx)
                fidx += 1
                label_dct[well_dct_key1] = fake_wellp_label

                pst_p_label = 'FPB' + str(chn_idx)
                label_dct[well_dct_key1.replace('F', 'FPB')] = pst_p_label
            if not fake_wellp_label:
                ioprinter.debug_message('label test', label_dct, well_dct_key1)
                fake_wellp_label = label_dct[well_dct_key1]
                if prods in (reacs, reacs[::-1]):
                    pst_p_label = label_dct[well_dct_key1.replace('F', 'FRB')]
                else:
                    pst_p_label = label_dct[well_dct_key1.replace('F', 'FPB')]
        else:
            fake_wellp_label = label_dct[well_dct_key1]

    label_dct[tsname] = 'B' + str(chn_idx)

    return label_dct

BIOBB_MD=$HOME/projects/biobb_md
cwltool $BIOBB_MD/cwl/gromacs/pdb2gmx.cwl $BIOBB_MD/cwl/test/gromacs/pdb2gmx.yml
cwltool $BIOBB_MD/cwl/gromacs/editconf.cwl $BIOBB_MD/cwl/test/gromacs/editconf.yml
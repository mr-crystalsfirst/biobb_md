#!/usr/bin/env python3

"""Module containing the AppendLigand class and the command line interface."""
import re
import argparse
import shutil
from pathlib import Path
from biobb_common.configuration import settings
from biobb_common.tools import file_utils as fu
from biobb_common.tools.file_utils import launchlogger


class AppendLigand:
    """This class takes a ligand ITP file and inserts it in a topology.

    Args:
        input_top_zip_path (str): Path the input topology TOP and ITP files zipball. File type: input. `Sample file <https://github.com/bioexcel/biobb_md/raw/master/biobb_md/test/data/gromacs_extra/ndx2resttop.zip>`_. Accepted formats: zip.
        input_itp_path (str): Path to the ligand ITP file to be inserted in the topology. File type: input. `Sample file <https://github.com/bioexcel/biobb_md/raw/master/biobb_md/test/data/gromacs_extra/pep_ligand.itp>`_. Accepted formats: itp.
        output_top_zip_path (str): Path/Name the output topology TOP and ITP files zipball. File type: output. `Sample file <https://github.com/bioexcel/biobb_md/raw/master/biobb_md/test/reference/gromacs_extra/ref_appendligand.zip>`_. Accepted formats: zip.
        properties (dic):
            * **posres_name** (*str*) - ("POSRES_LIGAND") String to be included in the ifdef clause.
            * **remove_tmp** (*bool*) - (True) [WF property] Remove temporal files.
            * **restart** (*bool*) - (False) [WF property] Do not execute if output files exist.
    """

    def __init__(self, input_top_zip_path: str, input_itp_path: str, output_top_zip_path: str,
                 input_posres_itp_path: str = None, properties: dict = None, **kwargs) -> None:
        properties = properties or {}

        # Input/Output files
        self.io_dict = {
            "in": {"input_top_zip_path": input_top_zip_path, "input_itp_path": input_itp_path,
                   "input_posres_itp_path": input_posres_itp_path},
            "out": {"output_top_zip_path": output_top_zip_path}
        }

        # Properties specific for BB
        self.posres_name = properties.get('posres_name', 'POSRES_LIGAND')

        # Properties common in all BB
        self.can_write_console_log = properties.get('can_write_console_log', True)
        self.global_log = properties.get('global_log', None)
        self.prefix = properties.get('prefix', None)
        self.step = properties.get('step', None)
        self.path = properties.get('path', '')
        self.remove_tmp = properties.get('remove_tmp', True)
        self.restart = properties.get('restart', False)

        # Check the properties
        fu.check_properties(self, properties)

    @launchlogger
    def launch(self) -> int:
        """Launches the execution of the GROMACS editconf module."""
        tmp_files = []

        # Get local loggers from launchlogger decorator
        out_log = getattr(self, 'out_log', None)
        err_log = getattr(self, 'err_log', None)

        # Restart if needed
        if self.restart:
            output_file_list = [self.io_dict['out'].get("output_top_zip_path")]
            if fu.check_complete_files(output_file_list):
                fu.log('Restart is enabled, this step: %s will the skipped' % self.step, out_log, self.global_log)
                return 0

        # Unzip topology
        top_file = fu.unzip_top(zip_file=self.io_dict['in'].get("input_top_zip_path"), out_log=out_log)
        top_dir = str(Path(top_file).parent)
        tmp_files.append(top_dir)
        itp_name = str(Path(self.io_dict['in'].get("input_itp_path")).name)

        with open(top_file) as top_f:
            top_lines = top_f.readlines()
            top_f.close()
        fu.rm(top_file)

        forcefield_pattern = r'#include.*forcefield.itp\"'
        for index, line in enumerate(top_lines):
            if re.search(forcefield_pattern, line):
                break
        top_lines.insert(index+1, '\n')
        top_lines.insert(index+2, '; Including ligand ITP\n')
        top_lines.insert(index+3, '#include "' + itp_name + '"\n')
        top_lines.insert(index+4, '\n')
        if self.io_dict['in'].get("input_posres_itp_path"):
            top_lines.insert(index+5, '; Ligand position restraints'+'\n')
            top_lines.insert(index+6, '#ifdef '+self.posres_name+'\n')
            top_lines.insert(index+7, '#include "'+str(Path(self.io_dict['in'].get("input_posres_itp_path")).name)+'"\n')
            top_lines.insert(index+8, '#endif'+'\n')
            top_lines.insert(index+9, '\n')

        inside_moleculetype_section = False
        with open(self.io_dict['in'].get("input_itp_path")) as itp_file:
            moleculetype_pattern = r'\[ moleculetype \]'
            for line in itp_file:
                if re.search(moleculetype_pattern, line):
                    inside_moleculetype_section = True
                    continue
                if inside_moleculetype_section and not line.startswith(';'):
                    moleculetype = line.strip().split()[0].strip()
                    break

        molecules_pattern = r'\[ molecules \]'
        inside_molecules_section = False
        index_molecule = None
        molecule_string = moleculetype+(20-len(moleculetype))*' '+'1'+'\n'
        for index, line in enumerate(top_lines):
            if re.search(molecules_pattern, line):
                inside_molecules_section = True
                continue
            if inside_molecules_section and not line.startswith(';') and line.upper().startswith('PROTEIN'):
                index_molecule = index

        if index_molecule:
            top_lines.insert(index_molecule+1, molecule_string)
        else:
            top_lines.append(molecule_string)

        new_top = fu.create_name(path=top_dir, prefix=self.prefix, step=self.step, name='ligand.top')

        with open(new_top, 'w') as new_top_f:
            new_top_f.write("".join(top_lines))

        shutil.copy2(self.io_dict['in'].get("input_itp_path"), top_dir)
        if self.io_dict['in'].get("input_posres_itp_path"):
            shutil.copy2(self.io_dict['in'].get("input_posres_itp_path"), top_dir)

        # zip topology
        fu.log('Compressing topology to: %s' % self.io_dict['out'].get("output_top_zip_path"), out_log, self.global_log)
        fu.zip_top(zip_file=self.io_dict['out'].get("output_top_zip_path"), top_file=new_top, out_log=out_log)

        if self.remove_tmp:
            fu.rm_file_list(tmp_files, out_log=out_log)

        return 0


def main():
    parser = argparse.ArgumentParser(description="Wrapper of the GROMACS editconf module.",
                                     formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, width=99999))
    parser.add_argument('-c', '--config', required=False, help="This file can be a YAML file, JSON file or JSON string")

    # Specific args of each building block
    required_args = parser.add_argument_group('required arguments')
    required_args.add_argument('--input_top_zip_path', required=True)
    required_args.add_argument('--input_itp_path', required=True)
    required_args.add_argument('--output_top_zip_path', required=True)

    args = parser.parse_args()
    config = args.config if args.config else None
    properties = settings.ConfReader(config=config).get_prop_dic()
    
    # Specific call of each building block
    AppendLigand(input_top_zip_path=args.input_top_zip_path, input_itp_path=args.input_itp_path,
                 output_top_zip_path=args.output_top_zip_path, properties=properties).launch()


if __name__ == '__main__':
    main()

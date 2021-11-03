"""
MDSuite: A Zincwarecode package.

License
-------
This program and the accompanying materials are made available under the terms
of the Eclipse Public License v2.0 which accompanies this distribution, and is
available at https://www.eclipse.org/legal/epl-v20.html

SPDX-License-Identifier: EPL-2.0

Copyright Contributors to the Zincwarecode Project.

Contact Information
-------------------
email: zincwarecode@gmail.com
github: https://github.com/zincware
web: https://zincwarecode.com/

Citation
--------
If you use this module please cite us with:
"""
import mdsuite.file_io.file_read
import numpy as np
import copy

var_names = {
    "Positions": ["x", "y", "z"],
    "Scaled_Positions": ["xs", "ys", "zs"],
    "Unwrapped_Positions": ["xu", "yu", "zu"],
    "Scaled_Unwrapped_Positions": ["xsu", "ysu", "zsu"],
    "Velocities": ["vx", "vy", "vz"],
    "Forces": ["fx", "fy", "fz"],
    "Box_Images": ["ix", "iy", "iz"],
    "Dipole_Orientation_Magnitude": ["mux", "muy", "muz"],
    "Angular_Velocity_Spherical": ["omegax", "omegay", "omegaz"],
    "Angular_Velocity_Non_Spherical": ["angmomx", "angmomy", "angmomz"],
    "Torque": ["tqx", "tqy", "tqz"],
    "Charge": ["q"],
    "KE": ["c_KE"],
    "PE": ["c_PE"],
    "Stress": [
        "c_Stress[1]",
        "c_Stress[2]",
        "c_Stress[3]",
        "c_Stress[4]",
        "c_Stress[5]",
        "c_Stress[6]",
    ],
}


class LAMMPSTrajectoryFile(mdsuite.file_io.file_read.FileProcessor):
    """
    Reader for LAMMPS files
    """

    def __init__(self, file_path: str, trajectory_is_sorted_by_ids=True):
        self.file_path = file_path
        self.n_header_lines = 9
        self.trajectory_is_sorted_by_ids = trajectory_is_sorted_by_ids

        self._n_configurations_read = 0

        # attributes that will be filled in by get_metadata() and are later used by get_next_n_configurations()
        self._id_column_idx = None
        self._n_particles = None
        self._species_dict = None
        self._property_dict = None
        self._mdata = None

    def get_metadata(self) -> mdsuite.file_io.file_read.TrajectoryMetadata:
        """
        Gets the metadata for database creation.
        Also creates the lookup dictionaries on where to find the particles and properties in the file
        """
        with open(self.file_path, 'r') as file:
            header = mdsuite.file_io.file_read.read_n_lines(file, self.n_header_lines, start_at=0)

            # extract data that can be directly read off the header
            self._n_particles = int(header[3].split()[0])
            header_boxl_lines = header[5:8]
            box_l = [float(line.split()[1]) - float(line.split()[0]) for line in header_boxl_lines]

            # extract properties from the column names
            header_property_names = header[8].split()[2:]
            self._id_column_idx = header_property_names.index('id')
            self._property_dict = mdsuite.file_io.file_read.extract_properties_from_header(
                header_property_names, copy.deepcopy(var_names))

            # get number of configs from file length
            file.seek(0)
            num_lines = sum(1 for _ in file)
            n_configs_float = num_lines / (self._n_particles + self.n_header_lines)
            n_configs = int(round(n_configs_float))
            assert abs(n_configs_float - n_configs) < 1e-10

            # get information on which particles with which id belong to which species
            # by analysing the first configuration
            file.seek(0)
            self._species_dict = self._get_species_information(file, header_property_names)

            # extract sampe step information from consecutive headers
            file.seek(0)
            sample_step = self._get_sample_step(file)

        properties_list = list()
        for key, val in self._property_dict:
            properties_list.append(mdsuite.file_io.file_read.PropertyInfo(name=key, n_dims=len(val)))

        species_list = list()
        for key, val in self._species_dict.items():
            species_list.append(mdsuite.file_io.file_read.SpeciesInfo(name=key,
                                                                      n_particles=len(val),
                                                                      properties=properties_list))

        mdata = mdsuite.file_io.file_read.TrajectoryMetadata(n_configurations=n_configs,
                                                             species_list=species_list,
                                                             box_l=box_l,
                                                             sample_step=sample_step)
        self._mdata = mdata
        return mdata

    def get_next_n_configurations(self, n_configs: int) -> dict:
        lines_total_per_config = self.n_header_lines + self._n_particles
        read_start = self._n_configurations_read * lines_total_per_config

        ret_dict = dict()
        for sp_info in self._mdata.species_list:
            for prop_info in sp_info.properties:
                ret_dict[sp_info.name][prop_info.name] = np.zeros((sp_info.n_particles, n_configs, prop_info.n_dims))

        with open(self.file_path, 'r') as file:
            file.seek(read_start)
            for i in range(n_configs):
                # skip the header
                file.seek(self.n_header_lines, whence=1)
                # read one config
                traj_data = np.stack([np.array(list(file.readline().split())) for _ in self._n_particles])
                # sort by id
                if not self.trajectory_is_sorted_by_ids:
                    traj_data = sort_array_by_column(traj_data, self._id_column_idx)

                # slice by species
                for sp_info in self._mdata.species_list:
                    idxs = self._species_dict[sp_info.name]['line_idxs']
                    sp_data = traj_data[idxs, :]
                    # slice by property
                    for prop_info in sp_info.properties:
                        prop_column_idxs = self._property_dict[prop_info.name]
                        ret_dict[sp_info.name][prop_info.name][:, i, :] = sp_data[:, prop_column_idxs]

        self._n_configurations_read += n_configs

        return ret_dict

    def _get_species_information(self, file, header_property_names):
        """
        Get the information which species are present and which particle ids/ lines in the file belong to them

        Parameters
        ----------
        number_of_atoms : int
                Number of atoms in each configuration
        """
        header_id_index = header_property_names.index("id")
        #
        # Look for element keyword in trajectory.
        if "element" in header_property_names:
            header_species_index = header_property_names.index("element")
        # Look for type keyword if element is not present.
        elif "type" in header_property_names:
            header_species_index = header_property_names.index("type")
        # Raise an error if no identifying keywords are found.
        else:
            raise ValueError("Insufficient species or type identification available.")

        species_dict = dict()
        file.seek(self.n_header_lines)

        for i in range(self._n_particles):
            # read one configuration
            traj_data = np.stack([np.array(list(file.readline().split())) for _ in range(self._n_particles)])
            # sort by particle id
            if not self.trajectory_is_sorted_by_ids:
                traj_data = sort_array_by_column(traj_data, header_id_index)
            # iterate over the first configuration, whenever a new species (value at species_index) is encountered,
            # add an entry
            for i, line in enumerate(traj_data):
                species_name = line[header_species_index]
                particle_id = int(line[header_id_index])
                if species_name not in species_dict.keys():
                    species_dict[species_name] = {'particle_ids': [particle_id],
                                                  'line_idxs': [i]}
                else:
                    species_dict[species_name]['particle_ids'].append(particle_id)
                    species_dict[species_name]['line_idxs'].append(i)

        return species_dict


    def _get_sample_step(self, file):
        first_header = mdsuite.file_io.file_read.read_n_lines(file, self.n_header_lines, start_at=0)
        time_0 = float(first_header[1])  # Time in first configuration
        second_header = mdsuite.file_io.file_read.read_n_lines(file, self.n_header_lines,
                                                               start_at=self.n_header_lines + self._n_particles)
        time_1 = float(second_header[1])  # Time in second configuration

        return time_1 - time_0

def sort_array_by_column(array: np.ndarray, column_idx):
    # https://stackoverflow.com/questions/2828059/sorting-arrays-in-numpy-by-column/35624868
    return array[array[:, column_idx].argsort()]

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

Summary
-------
"""
import logging
import numpy as np
from scipy.signal import find_peaks
from mdsuite.utils.exceptions import NotApplicableToAnalysis
from mdsuite.calculators.calculator import Calculator, call
from mdsuite.utils.meta_functions import golden_section_search
from mdsuite.utils.meta_functions import apply_savgol_filter
from mdsuite.utils.units import boltzmann_constant
from bokeh.models import BoxAnnotation
from mdsuite.database.scheme import Computation

log = logging.getLogger(__name__)


class PotentialOfMeanForce(Calculator):
    """
    Class for the calculation of the potential of mean-force

    The potential of mean-force is a measure of the binding strength between
    atomic species in a experiment.

    Attributes
    ----------
    experiment : class object
                        Class object of the experiment.
    data_range : int (default=500)
                        Range over which the property should be evaluated.
                        This is not applicable to the current analysis as the
                        full rdf will be calculated.
    x_label : str
                        How to label the x axis of the saved plot.
    y_label : str
                        How to label the y axis of the saved plot.
    analysis_name : str
                        Name of the analysis. used in saving of the
                        tensor_values and figure.
    file_to_study : str
                        The tensor_values file corresponding to the rdf being
                        studied.
    data_files : list
                        list of files to be analyzed.
    rdf = None : list
                        rdf tensor_values being studied.
    radii = None : list
                        radii tensor_values corresponding to the rdf.
    selected_species : list
                        A list of species combinations being studied.

    See Also
    --------
    mdsuite.calculators.calculator.Calculator class

    Examples
    --------
    experiment.run_computation.PotentialOfMeanForce(savgol_order = 2,
                                                    savgol_window_length = 17)
    """

    def __init__(self, **kwargs):
        """
        Python constructor for the class

        Parameters
        ----------
        experiment : class object
                        Class object of the experiment.
        experiments : class object
                        Class object of the experiment.
        load_data : bool
        """

        super().__init__(**kwargs)
        self.file_to_study = None
        self.rdf = None
        self.radii = None
        self.pomf = None
        self.indices = None
        self.database_group = "Potential_Of_Mean_Force"
        self.x_label = r"$$\text{r| /  \AA$$"
        self.y_label = r"$$w^{(2)}(r)$$"

        self.result_keys = ["min_pomf", "uncertainty", "left", "right"]
        self.result_series_keys = ["r", "pomf"]

        self.analysis_name = "Potential_of_Mean_Force"
        self.post_generation = True

    @call
    def __call__(
        self,
        plot=True,
        save=True,
        data_range=1,
        export: bool = False,
        savgol_order: int = 2,
        savgol_window_length: int = 17,
    ) -> Computation:
        """
        Python constructor for the class

        Parameters
        ----------
        plot : bool (default=True)
                            Decision to plot the analysis.
        save : bool (default=True)
                            Decision to save the generated tensor_values arrays.

        data_range : int (default=500)
                            Range over which the property should be evaluated.
                            This is not applicable to the current analysis as
                            the full rdf will be calculated.
        export : bool
                If true, export the data directly to a csv.
        savgol_order : int
                Order of the savgol polynomial filter
        savgol_window_length : int
                Window length of the savgol filter.
        """
        self.update_user_args(
            plot=plot, save=save, data_range=data_range, export=export
        )
        self.data_files = []
        self.savgol_order = savgol_order
        self.savgol_window_length = savgol_window_length

        return self.update_db_entry_with_kwargs(
            data_range=data_range,
            savgol_order=savgol_order,
            savgol_window_length=savgol_window_length,
        )

    def _autocorrelation_time(self):
        """
        Not needed in this analysis
        """
        raise NotApplicableToAnalysis

    def _calculate_potential_of_mean_force(self):
        """
        Calculate the potential of mean force
        """

        self.pomf = (
            -1 * boltzmann_constant * self.experiment.temperature * np.log(self.rdf)
        )

    def _get_max_values(self):
        """
        Calculate the maximums of the rdf
        """
        filtered_data = apply_savgol_filter(
            self.pomf, order=self.savgol_order, window_length=self.savgol_window_length
        )

        # Find the maximums in the filtered dataset
        peaks = find_peaks(filtered_data)[0]

        return [peaks[0], peaks[1]]

    def _find_minimum(self):
        """
        Find the minimum of the pomf function

        This function calls an implementation of the Golden-section search
        algorithm to determine the minimum of the potential of mean-force function.

        Returns
        -------
        pomf_indices : list
                Location of the minimums of the pomf values.
        """

        peaks = (
            self._get_max_values()
        )  # get the peaks of the tensor_values post-filtering

        # Calculate the radii of the minimum range
        pomf_radii = golden_section_search(
            [self.radii, self.pomf], self.radii[peaks[1]], self.radii[peaks[0]]
        )

        pomf_indices = list(
            [
                np.where(self.radii == pomf_radii[0])[0][0],
                np.where(self.radii == pomf_radii[1])[0][0],
            ]
        )

        return pomf_indices

    def _get_pomf_value(self):
        """
        Use a min-finding algorithm to calculate the potential of mean force value
        """

        self.indices = (
            self._find_minimum()
        )  # update the class with the minimum value indices

        # Calculate the value and error of the potential of mean-force
        pomf_value = np.mean([self.pomf[self.indices[0]], self.pomf[self.indices[1]]])
        pomf_error = np.std(
            [self.pomf[self.indices[0]], self.pomf[self.indices[1]]]
        ) / np.sqrt(2)

        return pomf_value, pomf_error

    def run_post_generation_analysis(self):
        """
        Calculate the potential of mean-force and perform error analysis
        """
        # fill the tensor_values array with tensor_values
        calculations = self.experiment.run.RadialDistributionFunction(plot=False)
        self.data_range = calculations.data_range
        for selected_species, vals in calculations.data_dict.items():
            self.selected_species = selected_species.split("_")

            self.radii = np.array(vals["x"]).astype(float)[1:]
            self.rdf = np.array(vals["y"]).astype(float)[1:]

            log.debug(f"rdf: {self.rdf} \t radii: {self.radii}")
            self._calculate_potential_of_mean_force()
            (
                pomf_value,
                pomf_error,
            ) = (
                self._get_pomf_value()
            )  # Determine the min values of the function and update experiment

            data = {
                self.result_keys[0]: pomf_value.tolist(),
                self.result_keys[1]: pomf_error.tolist(),
                self.result_keys[2]: self.radii[self.indices[0]],
                self.result_keys[3]: self.radii[self.indices[1]],
                self.result_series_keys[0]: self.radii.tolist(),
                self.result_series_keys[1]: self.pomf.tolist(),
            }

            self.queue_data(data=data, subjects=self.selected_species)

    def plot_data(self, data):
        """Plot the POMF"""
        log.debug("Start plotting the POMF.")
        for selected_species, val in data.items():
            model = BoxAnnotation(
                left=val[self.result_keys[2]],
                right=val[self.result_keys[3]],
                fill_alpha=0.1,
                fill_color="red",
            )
            self.run_visualization(
                x_data=val[self.result_series_keys[0]],
                y_data=val[self.result_series_keys[1]],
                title=(
                    fr"{selected_species}: {val[self.result_keys[0]]: 0.3E} +-"
                    fr" {val[self.result_keys[1]]: 0.3E}"
                ),
                layouts=[model],
            )

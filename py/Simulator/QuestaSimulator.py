# EMACS settings: -*-	tab-width: 2; indent-tabs-mode: t; python-indent-offset: 2 -*-
# vim: tabstop=2:shiftwidth=2:noexpandtab
# kate: tab-width 2; replace-tabs off; indent-width 2;
#
# ==============================================================================
# Authors:          Patrick Lehmann
#                   Martin Zabel
#
# Python Class:      TODO
#
# Description:
# ------------------------------------
#		TODO:
#
# License:
# ==============================================================================
# Copyright 2007-2016 Technische Universitaet Dresden - Germany
#                     Chair for VLSI-Design, Diagnostics and Architecture
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
#
# entry point
if __name__ != "__main__":
	# place library initialization code here
	pass
else:
	from lib.Functions import Exit
	Exit.printThisIsNoExecutableFile("The PoC-Library - Python Module Simulator.vSimSimulator")


# load dependencies
from pathlib                      import Path

from Base.Exceptions              import NotConfiguredException
from Base.Project                 import FileTypes, VHDLVersion, ToolChain, Tool
from Base.Simulator               import SimulatorException, Simulator as BaseSimulator, VHDL_TESTBENCH_LIBRARY_NAME, SkipableSimulatorException
from PoC.Config                   import Vendors
from ToolChains.Mentor.QuestaSim  import QuestaSim, QuestaException


class Simulator(BaseSimulator):
	_TOOL_CHAIN =            ToolChain.Mentor_QuestaSim
	_TOOL =                  Tool.Mentor_vSim

	def __init__(self, host, dryRun, guiMode):
		super().__init__(host, dryRun)

		self._guiMode =       guiMode
		self._vhdlVersion =   None
		self._vhdlGenerics =  None
		self._toolChain =     None

		vSimSimulatorFiles =            host.PoCConfig['CONFIG.DirectoryNames']['QuestaSimFiles']
		self.Directories.Working =      host.Directories.Temp / vSimSimulatorFiles
		self.Directories.PreCompiled =  host.Directories.PreCompiled / vSimSimulatorFiles

		self._PrepareSimulationEnvironment()
		self._PrepareSimulator()

	def _PrepareSimulator(self):
		# create the QuestaSim executable factory
		self._LogVerbose("Preparing Mentor simulator.")
		for sectionName in ['INSTALL.Mentor.QuestaSim', 'INSTALL.Altera.ModelSim']:
			if (len(self.Host.PoCConfig.options(sectionName)) != 0):
				break
		else:
			raise NotConfiguredException(
				"Neither Mentor Graphics QuestaSim nor ModelSim Altera-Edition are configured on this system.")

		questaSection = self.Host.PoCConfig[sectionName]
		binaryPath = Path(questaSection['BinaryDirectory'])
		version = questaSection['Version']
		self._toolChain = QuestaSim(self.Host.Platform, self.DryRun, binaryPath, version, logger=self.Logger)

	def Run(self, testbench, board, vhdlVersion, vhdlGenerics=None, guiMode=False):
		# TODO: refactor into a ModelSim module, shared by QuestaSim and Cocotb (-> MixIn class)?
		# select modelsim.ini
		self._modelsimIniPath = self.Directories.PreCompiled
		if board.Device.Vendor is Vendors.Altera:
			self._modelsimIniPath /= self.Host.PoCConfig['CONFIG.DirectoryNames']['AlteraSpecificFiles']
		elif board.Device.Vendor is Vendors.Lattice:
			self._modelsimIniPath /= self.Host.PoCConfig['CONFIG.DirectoryNames']['LatticeSpecificFiles']
		elif board.Device.Vendor is Vendors.Xilinx:
			self._modelsimIniPath  /= self.Host.PoCConfig['CONFIG.DirectoryNames']['XilinxSpecificFiles']

		self._modelsimIniPath /= "modelsim.ini"
		if not self._modelsimIniPath.exists():
			raise SimulatorException("Modelsim ini file '{0!s}' not found.".format(self._modelsimIniPath)) \
				from FileNotFoundError(str(self._modelsimIniPath))

		super().Run(testbench, board, vhdlVersion, vhdlGenerics, guiMode)

	def _RunAnalysis(self, _):
		# create a QuestaVHDLCompiler instance
		vlib = self._toolChain.GetVHDLLibraryTool()
		for lib in self._pocProject.VHDLLibraries:
			vlib.Parameters[vlib.SwitchLibraryName] = lib.Name
			vlib.CreateLibrary()

		# create a QuestaVHDLCompiler instance
		vcom = self._toolChain.GetVHDLCompiler()
		vcom.Parameters[vcom.FlagQuietMode] =         True
		vcom.Parameters[vcom.FlagExplicit] =          True
		vcom.Parameters[vcom.FlagRangeCheck] =        True
		vcom.Parameters[vcom.SwitchModelSimIniFile] = self._modelsimIniPath.as_posix()
		vcom.Parameters[vcom.SwitchVHDLVersion] =     repr(self._vhdlVersion)

		# run vcom compile for each VHDL file
		for file in self._pocProject.Files(fileType=FileTypes.VHDLSourceFile):
			if (not file.Path.exists()):              raise SimulatorException("Cannot analyse '{0!s}'.".format(file.Path)) from FileNotFoundError(str(file.Path))

			vcomLogFile = self.Directories.Working / (file.Path.stem + ".vcom.log")
			vcom.Parameters[vcom.SwitchVHDLLibrary] = file.LibraryName
			vcom.Parameters[vcom.ArgLogFile] =        vcomLogFile
			vcom.Parameters[vcom.ArgSourceFile] =     file.Path

			try:
				vcom.Compile()
			except QuestaException as ex:
				raise SimulatorException("Error while compiling '{0!s}'.".format(file.Path)) from ex
			if vcom.HasErrors:
				raise SkipableSimulatorException("Error while compiling '{0!s}'.".format(file.Path))

			# delete empty log files
			if (vcomLogFile.stat().st_size == 0):
				try:
					vcomLogFile.unlink()
				except OSError as ex:
					raise SimulatorException("Error while deleting '{0!s}'.".format(vcomLogFile)) from ex

	def _RunSimulation(self, testbench):
		if self._guiMode:
			return self._RunSimulationWithGUI(testbench)

		tclBatchFilePath =    self.Host.Directories.Root / self.Host.PoCConfig[testbench.ConfigSectionName]['vSimBatchScript']

		# create a QuestaSimulator instance
		vsim = self._toolChain.GetSimulator()
		vsim.Parameters[vsim.SwitchModelSimIniFile] = self._modelsimIniPath.as_posix()
		# vsim.Parameters[vsim.FlagOptimization] =      True			# FIXME:
		vsim.Parameters[vsim.FlagReportAsError] =     "3473"
		vsim.Parameters[vsim.SwitchTimeResolution] =  "1fs"
		vsim.Parameters[vsim.FlagCommandLineMode] =   True
		vsim.Parameters[vsim.SwitchBatchCommand] =    "do {0}".format(tclBatchFilePath.as_posix())
		vsim.Parameters[vsim.SwitchTopLevel] =        "{0}.{1}".format(VHDL_TESTBENCH_LIBRARY_NAME, testbench.ModuleName)
		testbench.Result = vsim.Simulate()

	def _RunSimulationWithGUI(self, testbench):
		tclGUIFilePath =      self.Host.Directories.Root / self.Host.PoCConfig[testbench.ConfigSectionName]['vSimGUIScript']
		tclWaveFilePath =      self.Host.Directories.Root / self.Host.PoCConfig[testbench.ConfigSectionName]['vSimWaveScript']

		# create a QuestaSimulator instance
		vsim = self._toolChain.GetSimulator()
		vsim.Parameters[vsim.SwitchModelSimIniFile] = self._modelsimIniPath.as_posix()
		# vsim.Parameters[vsim.FlagOptimization] =      True			# FIXME:
		vsim.Parameters[vsim.FlagReportAsError] =     "3473"
		vsim.Parameters[vsim.SwitchTimeResolution] =  "1fs"
		vsim.Parameters[vsim.FlagGuiMode] =           True
		vsim.Parameters[vsim.SwitchTopLevel] =        "{0}.{1}".format(VHDL_TESTBENCH_LIBRARY_NAME, testbench.ModuleName)
		# vsim.Parameters[vsim.SwitchTitle] =           testbenchName

		if (tclWaveFilePath.exists()):
			self._LogDebug("Found waveform script: '{0!s}'".format(tclWaveFilePath))
			vsim.Parameters[vsim.SwitchBatchCommand] =  "do {0}; do {1}".format(tclWaveFilePath.as_posix(), tclGUIFilePath.as_posix())
		else:
			self._LogDebug("Didn't find waveform script: '{0!s}'. Loading default commands.".format(tclWaveFilePath))
			vsim.Parameters[vsim.SwitchBatchCommand] =  "add wave *; do {0}".format(tclGUIFilePath.as_posix())

		testbench.Result = vsim.Simulate()

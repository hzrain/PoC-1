# EMACS settings: -*-	tab-width: 2; indent-tabs-mode: t; python-indent-offset: 2 -*-
# vim: tabstop=2:shiftwidth=2:noexpandtab
# kate: tab-width 2; replace-tabs off; indent-width 2;
#
# ==============================================================================
# Authors:          Patrick Lehmann
#                   Martin Zabel
#
# Python Class:      Aldec Active-HDL specific classes
#
# Description:
# ------------------------------------
#		TODO:
#		-
#		-
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
from subprocess import check_output


if __name__ != "__main__":
	# place library initialization code here
	pass
else:
	from lib.Functions import Exit
	Exit.printThisIsNoExecutableFile("PoC Library - Python Module ToolChains.Aldec.ActiveHDL")


from lib.Functions          import CallByRefParam
from Base.Exceptions        import PlatformNotSupportedException
from Base.Logging            import LogEntry, Severity
from Base.Simulator          import SimulationResult, PoCSimulationResultFilter
from Base.Executable        import Executable
from Base.Executable        import ExecutableArgument, PathArgument, StringArgument
from Base.Executable        import LongFlagArgument, ShortValuedFlagArgument, ShortTupleArgument, CommandLineArgumentList
from Base.Configuration      import Configuration as BaseConfiguration, ConfigurationException
from ToolChains.Aldec.Aldec  import AldecException


class ActiveHDLException(AldecException):
	pass


class Configuration(BaseConfiguration):
	_vendor =      "Aldec"
	_toolName =    "Aldec Active-HDL"
	_section  =    "INSTALL.Aldec.ActiveHDL"
	_template = {
		"Windows": {
			_section: {
				"Version":                "10.3",
				"InstallationDirectory":  "${INSTALL.Aldec:InstallationDirectory}/Active-HDL",
				"BinaryDirectory":        "${InstallationDirectory}/BIN"
			}
		},
		"Linux": {
			_section: {
			#		"Version":                "10.4c",
			#		"InstallationDirectory":  "${INSTALL.Aldec:InstallationDirectory}/${Version}",
			#		"BinaryDirectory":        "${InstallationDirectory}/bin"
			}
		}
	}

	def CheckDependency(self):
		# return True if Aldec is configured
		return (len(self._host.PoCConfig['INSTALL.Aldec']) != 0)

	def ConfigureForAll(self):
		try:
			if (not self._AskInstalled("Is Aldec Active-HDL installed on your system?")):
				self.ClearSection()
			else:
				version = self._ConfigureVersion()
				self._ConfigureInstallationDirectory()
				binPath = self._ConfigureBinaryDirectory()
				self.__CheckActiveHDLVersion(binPath, version)
		except ConfigurationException:
			self.ClearSection()
			raise

	def __CheckActiveHDLVersion(self, binPath, version):
		if (self._host.Platform == "Windows"):
			vsimPath = binPath / "vsim.exe"
		else:
			vsimPath = binPath / "vsim"

		if not vsimPath.exists():
			raise ConfigurationException("Executable '{0!s}' not found.".format(vsimPath)) from FileNotFoundError(
				str(vsimPath))

		output = check_output([str(vsimPath), "-version"], universal_newlines=True)
		if str(version) not in output:
			raise ConfigurationException("Active-HDL version mismatch. Expected version {0}.".format(version))


class ActiveHDLMixIn:
	def __init__(self, platform, dryrun, binaryDirectoryPath, version, logger=None):
		self._platform =            platform
		self._dryrun =              dryrun
		self._binaryDirectoryPath = binaryDirectoryPath
		self._version =             version
		self._logger =              logger


class ActiveHDL(ActiveHDLMixIn):
	def __init__(self, platform, dryrun, binaryDirectoryPath, version, logger=None):
		ActiveHDLMixIn.__init__(self, platform, dryrun, binaryDirectoryPath, version, logger)

	def GetVHDLLibraryTool(self):
		return ActiveHDLVHDLLibraryTool(self._platform, self._dryrun, self._binaryDirectoryPath, self._version, logger=self._logger)

	def GetVHDLCompiler(self):
		return VHDLCompiler(self._platform, self._dryrun, self._binaryDirectoryPath, self._version, logger=self._logger)

	def GetSimulator(self):
		return StandaloneSimulator(self._platform, self._dryrun, self._binaryDirectoryPath, self._version, logger=self._logger)


class VHDLCompiler(Executable, ActiveHDLMixIn):
	def __init__(self, platform, dryrun, binaryDirectoryPath, version, logger=None):
		ActiveHDLMixIn.__init__(self, platform, dryrun, binaryDirectoryPath, version, logger=logger)
		if (self._platform == "Windows"):    executablePath = binaryDirectoryPath / "vcom.exe"
		# elif (self._platform == "Linux"):    executablePath = binaryDirectoryPath / "vcom"
		else:                                            raise PlatformNotSupportedException(self._platform)
		super().__init__(platform, dryrun, executablePath, logger=logger)

		self._hasOutput =    False
		self._hasWarnings =  False
		self._hasErrors =    False

		self.Parameters[self.Executable] = executablePath

	@property
	def HasWarnings(self):
		return self._hasWarnings

	@property
	def HasErrors(self):
		return self._hasErrors

	class Executable(metaclass=ExecutableArgument):
		_value =  None

	class FlagNoRangeCheck(metaclass=LongFlagArgument):
		_name =    "norangecheck"
		_value =  None

	class SwitchVHDLVersion(metaclass=ShortValuedFlagArgument):
		_pattern =  "-{1}"
		_name =      ""
		_value =    None

	class SwitchVHDLLibrary(metaclass=ShortTupleArgument):
		_name =    "work"
		_value =  None

	class ArgSourceFile(metaclass=PathArgument):
		_value =  None

	Parameters = CommandLineArgumentList(
		Executable,
		FlagNoRangeCheck,
		SwitchVHDLVersion,
		SwitchVHDLLibrary,
		ArgSourceFile
	)

	# -reorder                      enables automatic file ordering
	# -O[0 | 1 | 2 | 3]             set optimization level
	# -93                                conform to VHDL 1076-1993
	# -2002                              conform to VHDL 1076-2002 (default)
	# -2008                              conform to VHDL 1076-2008
	# -relax                             allow 32-bit integer literals
	# -incr                              switching compiler to fast incremental mode

	def Compile(self):
		parameterList = self.Parameters.ToArgumentList()
		self._LogVerbose("command: {0}".format(" ".join(parameterList)))

		if (self._dryrun):
			self._LogDryRun("Start process: {0}".format(" ".join(parameterList)))
			return

		try:
			self.StartProcess(parameterList)
		except Exception as ex:
			raise ActiveHDLException("Failed to launch acom run.") from ex

		self._hasOutput = False
		self._hasWarnings = False
		self._hasErrors = False
		try:
			iterator = iter(VHDLCompilerFilter(self.GetReader()))
			line = next(iterator)


			self._hasOutput = True
			self._LogNormal("  acom messages for '{0}'".format(self.Parameters[self.ArgSourceFile]))
			self._LogNormal("  " + ("-" * (78 - self.Logger.BaseIndent*2)))

			while True:
				self._hasWarnings |= (line.Severity is Severity.Warning)
				self._hasErrors |= (line.Severity is Severity.Error)

				line.IndentBy(self.Logger.BaseIndent + 1)
				self._Log(line)
				line = next(iterator)

		except StopIteration:
			pass
		finally:
			if self._hasOutput:
				self._LogNormal("  " + ("-" * (78 - self.Logger.BaseIndent*2)))


class StandaloneSimulator(Executable, ActiveHDLMixIn):
	def __init__(self, platform, dryrun, binaryDirectoryPath, version, logger=None):
		ActiveHDLMixIn.__init__(self, platform, dryrun, binaryDirectoryPath, version, logger=logger)
		if (self._platform == "Windows"):    executablePath = binaryDirectoryPath / "vsimsa.exe"
		# elif (self._platform == "Linux"):    executablePath = binaryDirectoryPath / "vsimsa"
		else:                                            raise PlatformNotSupportedException(self._platform)
		super().__init__(platform, dryrun, executablePath, logger=logger)

		self._hasOutput =    False
		self._hasWarnings =  False
		self._hasErrors =    False

		self.Parameters[self.Executable] = executablePath

	@property
	def HasWarnings(self):
		return self._hasWarnings

	@property
	def HasErrors(self):
		return self._hasErrors

	class Executable(metaclass=ExecutableArgument):
		_value =  None

	class SwitchBatchCommand(metaclass=ShortTupleArgument):
		_name =    "do"
		_value =  None

	Parameters = CommandLineArgumentList(
		Executable,
		SwitchBatchCommand
	)

	def Simulate(self):
		parameterList = self.Parameters.ToArgumentList()
		self._LogVerbose("command: {0}".format(" ".join(parameterList)))
		self._LogDebug("tcl commands: {0}".format(self.Parameters[self.SwitchBatchCommand]))

		try:
			self.StartProcess(parameterList)
		except Exception as ex:
			raise ActiveHDLException("Failed to launch vsimsa run.") from ex

		self._hasOutput = False
		self._hasWarnings = False
		self._hasErrors = False
		simulationResult = CallByRefParam(SimulationResult.Error)
		try:
			iterator = iter(PoCSimulationResultFilter(SimulatorFilter(self.GetReader()), simulationResult))
			line = next(iterator)

			self._hasOutput = True
			self._LogNormal("  vsimsa messages for '{0}.{1}'".format("?????", "?????"))
			self._LogNormal("  " + ("-" * (78 - self.Logger.BaseIndent*2)))

			while True:
				self._hasWarnings |=  (line.Severity is Severity.Warning)
				self._hasErrors |=    (line.Severity is Severity.Error)

				line.IndentBy(self.Logger.BaseIndent + 1)
				self._Log(line)
				line = next(iterator)

		except StopIteration:
			pass
		finally:
			if self._hasOutput:
				self._LogNormal("  " + ("-" * (78 - self.Logger.BaseIndent*2)))

		return simulationResult.value


class Simulator(Executable, ActiveHDLMixIn):
	def __init__(self, platform, dryrun, binaryDirectoryPath, version, logger=None):
		ActiveHDLMixIn.__init__(self, platform, dryrun, binaryDirectoryPath, version, logger=logger)
		if (self._platform == "Windows"):    executablePath = binaryDirectoryPath / "vsimsa.exe"
		# elif (self._platform == "Linux"):    executablePath = binaryDirectoryPath / "vsimsa"
		else:                                            raise PlatformNotSupportedException(self._platform)
		super().__init__(platform, dryrun, executablePath, logger=logger)

		self.Parameters[self.Executable] = executablePath

	class Executable(metaclass=ExecutableArgument):
		_value =  None

	# class FlagVerbose(metaclass=ShortFlagArgument):
	# 	_name =    "v"
	# 	_value =  None
	#
	# class FlagOptimization(metaclass=ShortFlagArgument):
	# 	_name =    "vopt"
	# 	_value =  None
	#
	# class FlagCommandLineMode(metaclass=ShortFlagArgument):
	# 	_name =    "c"
	# 	_value =  None
	#
	# class SwitchTimeResolution(metaclass=ShortTupleArgument):
	# 	_name =    "t"
	# 	_value =  None

	class SwitchBatchCommand(metaclass=ShortTupleArgument):
		_name =    "do"

	# class SwitchTopLevel(metaclass=ShortValuedFlagArgument):
	# 	_name =    ""
	# 	_value =  None

	Parameters = CommandLineArgumentList(
		Executable,
		# FlagVerbose,
		# FlagOptimization,
		# FlagCommandLineMode,
		# SwitchTimeResolution,
		SwitchBatchCommand
		# SwitchTopLevel
	)

	# units = ("fs", "ps", "us", "ms", "sec", "min", "hr")

	def Simulate(self):
		parameterList = self.Parameters.ToArgumentList()

		self._LogVerbose("command: {0}".format(" ".join(parameterList)))
		self._LogDebug("tcl commands: {0}".format(self.Parameters[self.SwitchBatchCommand]))

		_indent = "    "
		print(_indent + "vsimsa messages for '{0}.{1}'".format("??????", "??????"))  # self.VHDLLibrary, topLevel))
		print(_indent + "-" * 80)
		try:
			self.StartProcess(parameterList)
			for line in self.GetReader():
				print(_indent + line)
		except Exception as ex:
			raise ex  # SimulatorException() from ex
		print(_indent + "-" * 80)


class ActiveHDLVHDLLibraryTool(Executable, ActiveHDLMixIn):
	def __init__(self, platform, dryrun, binaryDirectoryPath, version, logger=None):
		ActiveHDLMixIn.__init__(self, platform, dryrun, binaryDirectoryPath, version, logger=logger)
		if (self._platform == "Windows"):    executablePath = binaryDirectoryPath / "vlib.exe"
		# elif (self._platform == "Linux"):    executablePath = binaryDirectoryPath / "vlib"
		else:                                            raise PlatformNotSupportedException(self._platform)
		super().__init__(platform, dryrun, executablePath, logger=logger)

		self._hasOutput =    False
		self._hasWarnings =  False
		self._hasErrors =    False

		self.Parameters[self.Executable] = executablePath

	@property
	def HasWarnings(self):
		return self._hasWarnings

	@property
	def HasErrors(self):
		return self._hasErrors

	class Executable(metaclass=ExecutableArgument):
		_value =  None

	# class FlagVerbose(metaclass=FlagArgument):
	# 	_name =    "-v"
	# 	_value =  None

	class SwitchLibraryName(metaclass=StringArgument):
		_value =  None

	Parameters = CommandLineArgumentList(
		Executable,
		# FlagVerbose,
		SwitchLibraryName
	)

	def CreateLibrary(self):
		parameterList = self.Parameters.ToArgumentList()
		self._LogVerbose("command: {0}".format(" ".join(parameterList)))

		try:
			self.StartProcess(parameterList)
		except Exception as ex:
			raise ActiveHDLException("Failed to launch alib run.") from ex

		self._hasOutput = False
		self._hasWarnings = False
		self._hasErrors = False
		try:
			iterator = iter(VHDLLibraryToolFilter(self.GetReader()))
			line = next(iterator)

			self._hasOutput = True
			self._LogNormal("  alib messages for '{0}'".format(self.Parameters[self.SwitchLibraryName]))
			self._LogNormal("  " + ("-" * (78 - self.Logger.BaseIndent*2)))

			while True:
				self._hasWarnings |=  (line.Severity is Severity.Warning)
				self._hasErrors |=    (line.Severity is Severity.Error)

				line.IndentBy(self.Logger.BaseIndent + 1)
				self._Log(line)
				line = next(iterator)

		except StopIteration:
			pass
		finally:
			if self._hasOutput:
				self._LogNormal("  " + ("-" * (78 - self.Logger.BaseIndent*2)))


		# 			# assemble acom command as list of parameters
		# 			parameterList = [
		# 				str(aComExecutablePath),
		# 				'-O3',
		# 				'-relax',
		# 				'-l', 'acom.log',
		# 				vhdlStandard,
		# 				'-work', vhdlLibraryName,
		# 				str(vhdlFilePath)
		# 			]
		# parameterList = [
		# 	str(aSimExecutablePath)#,
		# 	# '-vopt',
		# 	# '-t', '1fs',
		# ]


def VHDLCompilerFilter(gen):
	for line in gen:
		if line.startswith("Aldec, Inc. VHDL Compiler"):
			yield LogEntry(line, Severity.Debug)
		elif line.startswith("DAGGEN WARNING DAGGEN_0523"):
			yield LogEntry(line, Severity.Debug)
		elif line.startswith("ACOMP Initializing"):
			yield LogEntry(line, Severity.Debug)
		elif line.startswith("VLM Initialized with path"):
			yield LogEntry(line, Severity.Verbose)
		elif line.startswith("VLM ERROR "):
			yield LogEntry(line, Severity.Error)
		elif line.startswith("COMP96 File: "):
			yield LogEntry(line, Severity.Verbose)
		elif line.startswith("COMP96 Compile Package "):
			yield LogEntry(line, Severity.Verbose)
		elif line.startswith("COMP96 Compile Entity "):
			yield LogEntry(line, Severity.Verbose)
		elif line.startswith("COMP96 Compile Architecture "):
			yield LogEntry(line, Severity.Verbose)
		elif line.startswith("COMP96 Compile success "):
			yield LogEntry(line, Severity.Verbose)
		elif line.startswith("COMP96 Compile failure "):
			yield LogEntry(line, Severity.Error)
		elif line.startswith("COMP96 WARNING "):
			yield LogEntry(line, Severity.Warning)
		elif line.startswith("ELAB1 WARNING ELAB1_0026:"):
			yield LogEntry(line, Severity.Warning)
		elif line.startswith("COMP96 ERROR "):
			yield LogEntry(line, Severity.Error)
		else:
			yield LogEntry(line, Severity.Normal)


def SimulatorFilter(gen):
	PoCOutputFound = False
	for line in gen:
		if line.startswith("asim"):
			yield LogEntry(line, Severity.Verbose)
		elif line.startswith("VSIM: "):
			yield LogEntry(line, Severity.Verbose)
		elif (line.startswith("ELBREAD: Warning: ") and line.endswith("not bound.")):
			yield LogEntry(line, Severity.Error)
		elif line.startswith("ELBREAD: "):
			yield LogEntry(line, Severity.Verbose)
		elif line.startswith("ELAB2: "):
			yield LogEntry(line, Severity.Verbose)
		elif line.startswith("SLP: "):
			yield LogEntry(line, Severity.Verbose)
		elif line.startswith("Allocation: "):
			yield LogEntry(line, Severity.Verbose)
		elif line.startswith("KERNEL: ========================================"):
			PoCOutputFound = True
			yield LogEntry(line[8:], Severity.Normal)
		elif line.startswith("KERNEL: "):
			if (not PoCOutputFound):
				yield LogEntry(line, Severity.Verbose)
			else:
				yield LogEntry(line[8:], Severity.Normal)
		else:
			yield LogEntry(line, Severity.Normal)

def VHDLLibraryToolFilter(gen):
	for line in gen:
		if line.startswith("ALIB: Library "):
			yield LogEntry(line, Severity.Verbose)
		else:
			yield LogEntry(line, Severity.Normal)

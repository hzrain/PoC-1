
ocram_wb
########

This slave supports Wishbone Registered Feedback bus cycles (aka. burst
transfers / advanced synchronous cycle termination). The mode "Incrementing
burst cycle" (CTI = 010) with "Linear burst" (BTE = 00) is supported.
If your master does support Wishbone Classis bus cycles only, then connect
wb_cti_i = "000" and wb_bte_i = "00".
Connect the ocram of your choice to the ram_* port signals. (Every RAM with
single cyle read latency is supported.)
Configuration:
--------------
PIPE_STAGES = 1: The RAM output is directly connected to the bus. Thus, the
  read access latency (one cycle) is short. But, the RAM's read timing delay
  must be respected.
PIPE_STAGES = 2: The RAM output is registered again. Thus, the read access
  latency is two cycles.


.. rubric:: Entity Declaration:

.. literalinclude:: ../../../../src/bus/wb/wb_ocram.vhdl
   :language: vhdl
   :tab-width: 2
   :linenos:
   :lines: 52-78

Source file: `bus/wb/wb_ocram.vhdl <https://github.com/VLSI-EDA/PoC/blob/master/src/bus/wb/wb_ocram.vhdl>`_


	 
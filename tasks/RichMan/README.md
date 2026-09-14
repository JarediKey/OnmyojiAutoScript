# Rich Man shop return

[简体中文](README.zh.md)

`MallNavbar.back_mall()` spaces yellow-back clicks at least 3 seconds apart while
waiting for the mall marker. Rich Man and Mystery Shop share this method.
Other return actions retain their own intervals.

This interval reduces rapid repeated returns during transitions. It does not
change the completion condition: arriving at the courtyard still does not satisfy
the mall marker, so that case can reach the existing stuck timeout. The interval
change has been checked locally; live game behavior has not been verified.

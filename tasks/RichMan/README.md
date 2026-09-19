# Rich Man shop return

[简体中文](README.zh.md)

`MallNavbar.back_mall()` spaces yellow-back clicks at least 3 seconds apart while
waiting for the mall marker. Rich Man and Mystery Shop share this method.
Other return actions retain their own intervals.

This interval reduces rapid repeated returns during transitions. It does not
change the completion condition: arriving at the courtyard still does not satisfy
the mall marker, so that case can reach the existing stuck timeout. The interval
change has been checked locally; live game behavior has not been verified.

Product-list icons in Honor, Charisma, Bondlings, Friendship, Scales, Special,
Medal, and Consignment use a 0.7 matching threshold (27 rules). Purchase
confirmations and scroll-end markers retain their existing thresholds. The
sold-out mystery-amulet icon in the account-3 incident scores approximately 0.72
and is recognized with this threshold. Icon detection is not purchase confirmation.


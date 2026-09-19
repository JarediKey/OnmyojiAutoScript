# Android user selection

[简体中文](README.zh.md)

Set **Script → Device → Android user ID** (`script.device.user_id`) to choose a
game copy installed in an Android user/profile. The default `-1` disables user
selection and retains the existing package detection and app control behavior.
`0` selects the primary user; positive values select an existing secondary user.
Read actual IDs with `adb -s <serial> shell pm list users`; desktop icon numbering
is not necessarily the Android user ID. Android documents these commands in its
[multi-user guide](https://source.android.com/docs/devices/admin/multi-user-testing).

With user selection enabled, automatic package detection searches only the chosen
user. Before the first task interacts with the device, and whenever OAS starts the
game, it validates the user, package installation, and launcher activity. It then
starts the target profile, force-stops the same package under every other user on
that emulator, and launches the target with an explicit `--user`. Other packages
and other emulators are not stopped. Foreground verification checks both the
resumed activity's user ID and package, waiting up to 30 seconds. Invalid targets,
failed commands, or an unconfirmed foreground request human takeover; OAS does not
fall back to another user. Existing automatic app-control permission
(`script.error.handle_error`) must be enabled.

Normal stop/restart operations also target the configured user. The setting does
not modify game account data or switch the desktop's OS user. It does not provide
parallel control of multiple clones, continuous monitoring of other clones, or
per-display screenshots/touch. Use one OAS controller for that emulator and stop
the instance before changing its user selection.

Validation consists of offline command/state tests and read-only MuMu capability
checks. Actual clone stopping, launching, and game login have not been live-tested.

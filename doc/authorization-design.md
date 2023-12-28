# Folder share authorization design

The high-level overview of the process is as follows:

1. The user instructs the client qube to mount folder `X` on the server qube.
2. dom0 asks the user "client qube wants to mount folder `X` on server qube".
3. The user responds accordingly.  If authorized, the connection is permitted and the client qube can successfully mount `X`.

![Authorization dialog example](./auth-dialog.png)

Note how the default Qubes policy argument mechanism is insufficient for the proposed interaction.

For one, it limits the argument size to 64 bytes, making it unsuitable for a wide possibility of paths the user might want to connect to.  Second, it doesn't actually convey the information that the client qube sent — it conveys a form of hobbled information that crucially does not include spaces, slashes, or other special characters, all of which are legitimate in POSIX paths.  Third, the way that the question is presented is not exactly usable.

## Implementation details

The circumstances lead us to consider the implementation of an alternative security mechanism, proposed here.

Instead of directly contacting the server qube, the client qube contacts dom0 instead, through a special service `ruddo.AuthorizeFolderAccess` (with a default `allow` policy targeted at dom0), requesting access to a specific path of the server qube (id est, two arguments, the requested path and the target qube).  The data mentioned is of course sanitized accordingly, and rejected if they do not conform to a canonical form.

dom0 can then pop up a dialog (shown above) explicitly designed for the purpose of allowing this policy decision.  This dialog will display the crucial information the user needs to know in order to make an informed decision:

1. The origin qube of the request.
2. The target qube of the request.
3. The folder it wants to request.
4. Whether the access should be one-time allow or always allow.

If the user accepts this, then the decision data will be stored in dom0, on a dictionary keyed by the first 64 characters of the SHA256 hash of (origin, target, folder) — we will call this hash the decision fingerprint.

Then dom0 creates (much like `policy.RegisterArgument` does today) a policy `allow` element (based on the decision the user made) that permits the client qube to access the server qube's `ruddo.ConnectToFolder` service (in charge of establishing the `diod` server-side of the file share service) but *only when the correct argument is supplied*.

The decision fingerprint is then returned to the client VM.

At this point, the client VM can invoke `ruddo.ConnectToFolder`` with argument `<fingerprint>` (which is normally default deny but has now been authorized).

When the client service starts, it will contact the dom0 `ruddo.QueryFolderAuthorization` service, passing it the supplied (trusted) argument containing the fingerprint.  The dom0 service, using the argument on the persisted decision dictionary, will obtain the target folder that the client qube wanted to connect to, as well as whether the decision is one-time allow or always allow.

The dom0 service responds to the client qube which folder this connection is allowed to mount.  If the decision was a one-time allow decision, then the dom0 service immediately deletes the corresponding policy that permitted the server-to-client access that one time.  This is expected to be safe since, at that point, the connection between the server and the client has already been established.

Having obtained the necessary pieces of the puzzle, all verified by a trusted component, the client can then safely establish the `diod` session that the server expects.

If dom0, however, replies to the query folder authorization RPC from the client with a `NAK`, then the client service can simply shut down and leave the server qube cold.

![Authorization implementation diagram](./auth-flow.png)

The [diagram can be downloaded here](./auth-flow.dia).

## Design questions

### How do users manage persistent authorization decisions?

They use the folder share manager that ships with the software:

![Folder share manager](./folder-share-manager.png)

### Why not use the existing interaction mechanism to ask dom0 for authorization?

We don't want the default policy decision-making service asking the customary allow/deny question, which would lead to confusion and bafflement when the user gets a second, more informative policy dialog later.

### Why not let the server qube RPC service be the one asking for authorization (directly or via dom0)?

If we allow the server qube to ask dom0 (and therefore the user) "may so-and-so to access /so/and/so?" then the *source* of the question is not trusted — dom0 cannot verify that the client qube is who it says it is.  Thus the design requires that the server ask *dom0* for authorization *first*, and then dom0 can use that information to inform the client whether it should or should not allow access.

If we allow the server qube to store and permit policy decisions, then a malicious client VM could tamper with the policy decisions and allow for information disclosure to other malicious client VMs on the system.

## Corner cases

* DispVMs: we prohibit always-allow access in those cases, since that could lead to intended access to a DispVM permitted today, but unintended access permitted to another DispVM (with the same random number) created months down the road.  The only case acceptable is to blanket deny or block, which is supported by the code.
* Access to dom0 will never be allowed.  The service `ruddo.ConnectToFolder` will simply not be made available.
* Loopback access will not be permitted either.
* It is possible for client qubes to request access to server folders that do not exist.  This is presumably fine given the alternative of unauthorized information disclosure.

# Deliverables

All deliverables have been completed and shipped at this time:

* ~~Service `ruddo.AuthorizeFolderAccess` deployed with Qubes dom0 package.~~
* ~~Service `ruddo.ConnectToFolder` deployed with Qubes template VM package.~~
* ~~Removal of existing policy and service which gives blanket access to VMs.~~
* ~~Mechanism for persisting and managing folder policy decisions and decision data.~~
* ~~UI for authorizing folder access.~~
* ~~UI for managing existing authorizations and adding new ones ahead of time.~~

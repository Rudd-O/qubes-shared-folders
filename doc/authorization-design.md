# Next-gen folder share authorization design

Initially, Qubes shared folders used standard Qubes RPC authentication to decide whether to grant access to the folders of a qube (called *server* in this document) initiated by another qube (called *client* in this document).

This happens through the client qube invoking the `ruddo.ShareFolder` RPC service on the server qube, which if successful causes the `diod` daemon to be started on the server VM and finally connected via file descriptors to the kernel `v9fs` file system module in the client VM.

This is perfectly adequate for the use case where the user wants to grant the client qube blanket read/write access to any folder in the server qube.  This is, however, inadequate if the user wants to grant different client qubes finer-grained access to specific subfolders.

Consider, for example, one scenario of a "file server" qube that acts as a repository of data for three other client qubes: `work`, `projectX` and `social`.  Our stipulated user may want to save some types of data to some folders in the file server qube, but may not want to mix them.  In this scenario, our user wants work data to be saved to `fileserver:/home/user/Work`, social data to be saved to `fileserver:/home/user/Memes`, and his project X (work-related) involves some data that should *also* be accessible to his work qube, but he does not desire to grant the project X workspace access to *all* the work data, so he decides to store project X data under `fileserver:/home/user/Work/projectX`.  We further stipulate in this scenario that shuttling files around manually using the `qvm-move` facilities would severely impede the user's enjoyment of the Qubes system he is running.

This setup naturally requires a more sophisticated access control mechanism than a simple yes/no policy decision.

# User interaction

What we propose is the following:

1. The user instructs the client qube to mount folder `X` on the server qube.
2. dom0 asks the user "client qube wants to mount folder `X` on server qube".
3. The user responds accordingly.  If authorized, the connection is permitted and the client qube can successfully mount `X`.

The Qubes policy argument mechanism is insufficient for the proposed interaction.  For one, it limits the argument size to 64 bytes, making it unsuitable for a wide possibility of paths the user might want to connect to.  Second, it doesn't actually convey the information that the client qube sent — it conveys a form of hobbled information that crucially does not include spaces, slashes, or other special characters, all of which are legitimate in POSIX paths.  Third, the way that the question is presented is not exactly usable.

# Implementation details

The circumstances lead us to consider the implementation of an alternative security mechanism, proposed here.

Instead of directly contacting the server qube, the client qube will contact dom0 instead, through a special service `ruddo.AuthorizeFolderAccess` (with a default `allow` policy targeted at dom0), requesting access to a specific path of the server qube (id est, two arguments, the requested path and the target qube).  The data mentioned will of course be sanitized accordingly, and rejected if they do not conform to a canonical form.

dom0 can then pop up a dialog explicitly designed for the purpose of allowing this policy decision.  This dialog will display the crucial information the user needs to know in order to make an informed decision:

1. The origin qube of the request.
2. The target qube of the request.
3. The folder it wants to request.
4. Whether the access should be one-time allow or always allow.

If the user accepts this, then the decision data will be stored in dom0, on a dictionary keyed by the first 64 characters of the SHA256 hash of (origin, target, folder) — we will call this hash the decision fingerprint.

Then dom0 will create (much like `policy.RegisterArgument` does today) a policy `allow` element (based on the decision the user made) that permits the client qube to access the server qube's `ruddo.ConnectToFolder` service (in charge of establishing the `diod` server-side of the file share service) but *only when the correct argument is supplied*.

The decision fingerprint will then be returned to the client VM.

At this point, the client VM can invoke `ruddo.ConnectToFolder+<fingerprint>` (which is normally default deny but has now been authorized).

When the client service starts, it will contact the dom0 `ruddo.QueryFolderAuthorization` service, passing it the supplied (trusted) argument containing the fingerprint.  The dom0 service, using the argument on the persisted decision dictionary, will obtain the target folder that the client qube wanted to connect to, as well as whether the decision is one-time allow or always allow.

The dom0 service responds to the client qube which folder this connection is allowed to mount.  If the decision was a one-time allow decision, then the dom0 service immediately deletes the corresponding policy element that permitted the server-to-client access one time.  This is expected to be safe since, at that point, the connection between the server and the client has already been established.

Having obtained the necessary pieces of the puzzle, all verified by a trusted component, the client can then safely establish the `diod` session that the server expects.

If dom0, however, replies to the query folder authorization RPC from the client with a `NAK`, then the client service can simply shut down and leave the server qube cold.

## Design questions

### Why not use the existing interaction mechanism to ask dom0 for authorization?

We don't want the default policy decision-making service asking the customary allow/deny question, which would lead to confusion and bafflement when the user gets a second, more informative policy dialog later.

### Why not let the server qube RPC service be the one asking for authorization (directly or via dom0)?

If we allow the server qube to ask dom0 (and therefore the user) "may so-and-so to access /so/and/so?" then the *source* of the question is not trusted — dom0 cannot verify that the client qube is who it says it is.  Thus the design requires that the server ask *dom0* for authorization *first*, and then dom0 can use that information to inform the client whether it should or should not allow access.

If we allow the server qube to store and permit policy decisions, then a malicious client VM could tamper with the policy decisions and allow for information disclosure to other malicious client VMs on the system.


## Corner cases

* How do we deal with DispVMs?  I think the reasonble thing to do is to prohibit always-allow access in those cases, since that could lead to intended access to a DispVM permitted today, but unintended access permitted to another DispVM (with the same random number) created months down the road.
* Access to dom0 will never be allowed.  The service `ruddo.ConnectToFolder` will simply not be made available.
* It is possible for client qubes to request access to server folders that do not exist.  This is presumably fine given the alternative of unauthorized information disclosure.

# Deliverables

* Service `ruddo.AuthorizeFolderAccess` deployed with Qubes dom0 package.
* Service `ruddo.ConnectToFolder` deployed with Qubes template VM package.
* Removal of existing policy and service which gives blanket access to VMs.
* Mechanism for persisting and managing folder policy decisions and decision data.
* UI for authorizing folder access.
* UI for managing existing authorizations and adding new ones ahead of time.

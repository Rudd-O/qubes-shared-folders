use p9::Server;
use std::collections::BTreeMap;
use std::fs;
use std::fs::File;
use std::io::ErrorKind;
use std::os::unix::io::FromRawFd;
use std::path::Path;

const EX_OK: i32 = 0;
const EX_SERVER_ERROR: i32 = 8;
const EX_USAGE: i32 = 64;

fn main() {
    let args: Vec<_> = std::env::args().collect();
    if args.len() < 4 {
        eprintln!("Usage: {} <readfd> <writefd> <mountpoint>", args[0]);
        eprintln!("Examples:");
        eprintln!("");
        eprintln!(
            "  {} 0 1 /export # serves /export by reading from stdin and writing to stdout",
            args[0]
        );
        eprintln!("");
        eprintln!("Note that the file descriptors passed must already be opened.",);
        std::process::exit(EX_USAGE);
    }

    let readfd = match args[1].parse::<i32>() {
        Ok(p) => p,
        Err(e) => {
            eprintln!("Invalid read file descriptor {}: {}", args[1], e);
            std::process::exit(64);
        }
    };
    let writefd = match args[2].parse::<i32>() {
        Ok(p) => p,
        Err(e) => {
            eprintln!("Invalid write file descriptor {}: {}", args[2], e);
            std::process::exit(EX_USAGE);
        }
    };

    match fs::metadata(&args[3]) {
        Ok(f) => {
            if !f.is_dir() {
                eprintln!("Path to export {} must be a directory", args[3]);
                std::process::exit(EX_USAGE);
            }
            f
        }
        Err(e) => {
            eprintln!("Path to export {} cannot be used: {}", args[3], e);
            std::process::exit(EX_USAGE);
        }
    };

    let mut readhalf: File;
    let mut writehalf: File;

    unsafe {
        readhalf = File::from_raw_fd(readfd);
        writehalf = File::from_raw_fd(writefd);
    }

    let root = Path::new(&args[3]);

    let mut server = match Server::new(root, BTreeMap::new(), BTreeMap::new()) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("Fatal error starting server: {}", e);
            std::process::exit(EX_SERVER_ERROR);
        }
    };

    loop {
        let res = server.handle_message(&mut readhalf, &mut writehalf);
        match res {
            Err(e) => {
                if e.kind() == ErrorKind::UnexpectedEof {
                    // Normal exit when client unmounts.
                    // OK, it isn't necessarily a normal exit, but the library does
                    // not seem to provide a facility to distinguish EOF in the
                    // course of operations from EOF when client unmounts and
                    // the file descriptor is closed.
                    std::process::exit(EX_OK);
                };
                eprintln!("Fatal error handling request from client: {} ({:?})", e, e);
                std::process::exit(EX_SERVER_ERROR);
            }
            _ => (),
        }
    }
}

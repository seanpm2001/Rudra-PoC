/*!
```rudra-poc
[target]
crate = "bunch"
version = "0.1.0"

[report]
issue_url = "https://github.com/krl/bunch/issues/1"
issue_date = 2020-11-12

[[bugs]]
analyzer = "SendSyncVariance"
bug_class = "SendSyncVariance"
bug_count = 2
```
!*/
#![forbid(unsafe_code)]

use bunch::Bunch;
use std::cell::Cell;
use std::sync::Arc;
use std::thread;

// A simple tagged union used to demonstrate problems with data races in Cell.
#[derive(Debug, Clone, Copy)]
enum RefOrInt<'a> {
    Ref(&'a u64),
    Int(u64),
}
static X: u64 = 0;

fn main() {
    let bunch = Bunch::new();
    let item_not_sync = Cell::new(RefOrInt::Ref(&X));
    bunch.push(item_not_sync);

    let arc_0 = Arc::new(bunch);
    let arc_1 = Arc::clone(&arc_0);

    let _child = thread::spawn(move || {
        let smuggled_cell = arc_1.get(0);

        loop {
            smuggled_cell.set(RefOrInt::Int(0xdeadbeef));
            smuggled_cell.set(RefOrInt::Ref(&X))
        }
    });

    loop {
        if let RefOrInt::Ref(addr) = arc_0.get(0).get() {
            if addr as *const _ as usize != 0xdeadbeef {
                continue;
            }
            // Due to the data race, obtaining Ref(0xdeadbeef) is possible
            println!("Pointer is now: {:p}", addr);
            println!("Dereferencing addr will now segfault: {}", *addr);
        }
    }
}

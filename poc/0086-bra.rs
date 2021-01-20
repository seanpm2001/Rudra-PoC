/*!
```rudra-poc
[target]
crate = "bra"
version = "0.1.0"

[test]
analyzers = ["UnsafeDataflow"]
bug_classes = ["UninitExposure"]

[report]
issue_url = "https://github.com/Enet4/bra-rs/issues/1"
issue_date = 2021-01-02
rustsec_url = "https://github.com/RustSec/advisory-db/pull/586"
rustsec_id = "RUSTSEC-2021-0008"
unique_bugs = 1
```
!*/
#![forbid(unsafe_code)]

fn main() {
    panic!("This issue was reported without PoC");
}

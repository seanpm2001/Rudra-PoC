/*!
```rudra-poc
[target]
crate = "gfx-auxil"
version = "0.7.0"

[report]
issue_url = "https://github.com/gfx-rs/gfx/issues/3567"
issue_date = 2021-01-07
rustsec_url = "https://github.com/RustSec/advisory-db/pull/681"

[[bugs]]
analyzer = "UnsafeDataflow"
bug_class = "UninitExposure"
rudra_report_locations = ["src/auxil/auxil/src/lib.rs:60:1: 96:2"]
```
!*/
#![forbid(unsafe_code)]

fn main() {
    panic!("This issue was reported without PoC");
}

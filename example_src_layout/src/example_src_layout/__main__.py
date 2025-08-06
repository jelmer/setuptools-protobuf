from example_src_layout import Example, Example2

example = Example()
example.description = "This is a description"
example.path = "path/to/example"

example2 = Example2()
example2.example.CopyFrom(example)

print(example)
print(example2)

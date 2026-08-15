{
  "cases": [
    {
      "case": "dedupe([1,2,2,3])",
      "expect": "[1,2,3]"
    },
    {
      "case": "dedupe(['a','a','b'])",
      "expect": "['a','b']"
    },
    {
      "case": "dedupe([])",
      "expect": "[]"
    }
  ]
}
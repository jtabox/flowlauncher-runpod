# Various GraphQL queries for the plugin

QUERY_MYSELF = '''
query myself {
  myself {
    currentSpendPerHr
    clientBalance
    pods {
        id
        adjustedCostPerHr
    }
  }
}
'''

from ...utils import get_graphql_content

PROMOTIONS_QUERY = """
query Promotions($first: Int, $sortBy: PromotionSortingInput) {
  promotions(first: $first, sortBy: $sortBy) {
    totalCount
    edges {
      node {
        id
        events {
          __typename
        }
        name
        createdAt
        rules {
          id
          name
          description
          rewardValueType
          cataloguePredicate
          rewardValue
          channels {
            name
          }
        }
      }
    }
  }
}
"""


def promotions_query(
    staff_api_client,
    first=10,
):
    variables = {"first": first, "sortBy": {"field": "CREATED_AT", "direction": "DESC"}}

    response = staff_api_client.post_graphql(
        PROMOTIONS_QUERY,
        variables,
    )

    content = get_graphql_content(response)

    data = content["data"]["promotions"]["edges"]

    return data

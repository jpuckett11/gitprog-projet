"""GitHub Discussions (GraphQL-only)."""

from __future__ import annotations

from typing import Any

from gitget.api.graphql import GraphQLClient
from gitget.models import Discussion

_LIST_QUERY = """
query ListDiscussions($owner: String!, $name: String!, $first: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    discussions(first: $first, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        id
        number
        title
        body
        url
        createdAt
        updatedAt
        locked
        answerChosenAt
        category { name }
        author { login }
        comments { totalCount }
      }
    }
  }
}
"""

_GET_QUERY = """
query GetDiscussion($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    discussion(number: $number) {
      id
      number
      title
      body
      url
      createdAt
      updatedAt
      locked
      answerChosenAt
      category { name }
      author { login }
      comments(first: 50) {
        nodes {
          id
          body
          createdAt
          author { login }
        }
      }
    }
  }
}
"""

_ADD_COMMENT = """
mutation AddDiscussionComment($discussionId: ID!, $body: String!) {
  addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {
    comment { id body createdAt author { login } }
  }
}
"""


class DiscussionsService:
    def __init__(self, graphql: GraphQLClient) -> None:
        self._graphql = graphql

    async def list_for_repo(
        self, owner: str, name: str, *, page_size: int = 30, max_pages: int = 5
    ) -> list[Discussion]:
        out: list[Discussion] = []
        cursor: str | None = None
        for _ in range(max_pages):
            data = await self._graphql.execute(
                _LIST_QUERY,
                {"owner": owner, "name": name, "first": page_size, "after": cursor},
            )
            repo = data.get("repository")
            if repo is None:
                return out
            d = repo["discussions"]
            for node in d["nodes"]:
                out.append(_node_to_discussion(node))
            if not d["pageInfo"]["hasNextPage"]:
                break
            cursor = d["pageInfo"]["endCursor"]
        return out

    async def get(self, owner: str, name: str, number: int) -> dict[str, Any]:
        """Returns the raw GraphQL discussion node including comments."""
        data = await self._graphql.execute(
            _GET_QUERY, {"owner": owner, "name": name, "number": number}
        )
        return data["repository"]["discussion"]

    async def add_comment(self, discussion_id: str, body: str) -> dict:
        data = await self._graphql.execute(
            _ADD_COMMENT, {"discussionId": discussion_id, "body": body}
        )
        return data["addDiscussionComment"]["comment"]


def _node_to_discussion(n: dict) -> Discussion:
    return Discussion(
        id=n["id"],
        number=n["number"],
        title=n["title"],
        body=n.get("body"),
        url=n["url"],
        category_name=(n.get("category") or {}).get("name"),
        answer_chosen_at=n.get("answerChosenAt"),
        created_at=n["createdAt"],
        updated_at=n["updatedAt"],
        comments_count=(n.get("comments") or {}).get("totalCount", 0),
        author_login=(n.get("author") or {}).get("login"),
        locked=n.get("locked", False),
    )

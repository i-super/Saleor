import gql from "graphql-tag";

import { TypedMutation } from "../mutations";
import { collectionDetailsFragment } from "./queries";
import {
  AssignHomepageCollection,
  AssignHomepageCollectionVariables
} from "./types/AssignHomepageCollection";
import {
  CollectionUpdate,
  CollectionUpdateVariables
} from "./types/CollectionUpdate";

const collectionUpdate = gql`
  ${collectionDetailsFragment}
  mutation CollectionUpdate($id: ID!, $input: CollectionInput!) {
    collectionUpdate(id: $id, input: $input) {
      errors {
        field
        message
      }
      collection {
        ...CollectionDetailsFragment
      }
    }
  }
`;
export const TypedCollectionUpdateMutation = TypedMutation<
  CollectionUpdate,
  CollectionUpdateVariables
>(collectionUpdate);

const assignHomepageCollection = gql`
  mutation AssignHomepageCollection($id: ID) {
    homepageCollectionUpdate(collection: $id) {
      errors {
        field
        message
      }
      shop {
        homepageCollection {
          id
        }
      }
    }
  }
`;
export const TypedAssignHomepageCollectionMutation = TypedMutation<
  AssignHomepageCollection,
  AssignHomepageCollectionVariables
>(assignHomepageCollection);

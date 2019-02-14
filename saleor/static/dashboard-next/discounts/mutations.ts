import gql from "graphql-tag";

import { TypedMutation } from "../mutations";
import { saleDetailsFragment, saleFragment } from "./queries";
import {
  SaleCataloguesAdd,
  SaleCataloguesAddVariables
} from "./types/SaleCataloguesAdd";
import {
  SaleCataloguesRemove,
  SaleCataloguesRemoveVariables
} from "./types/SaleCataloguesRemove";
import { SaleUpdate, SaleUpdateVariables } from "./types/SaleUpdate";

const saleUpdate = gql`
  ${saleFragment}
  mutation SaleUpdate($input: SaleInput!, $id: ID!) {
    saleUpdate(id: $id, input: $input) {
      errors {
        field
        message
      }
      sale {
        ...SaleFragment
      }
    }
  }
`;
export const TypedSaleUpdate = TypedMutation<SaleUpdate, SaleUpdateVariables>(
  saleUpdate
);

const saleCataloguesAdd = gql`
  ${saleDetailsFragment}
  mutation SaleCataloguesAdd(
    $input: CatalogueInput!
    $id: ID!
    $after: String
    $before: String
    $first: Int
    $last: Int
  ) {
    saleCataloguesAdd(id: $id, input: $input) {
      errors {
        field
        message
      }
      sale {
        ...SaleDetailsFragment
      }
    }
  }
`;
export const TypedSaleCataloguesAdd = TypedMutation<
  SaleCataloguesAdd,
  SaleCataloguesAddVariables
>(saleCataloguesAdd);

const saleCataloguesRemove = gql`
  ${saleDetailsFragment}
  mutation SaleCataloguesRemove(
    $input: CatalogueInput!
    $id: ID!
    $after: String
    $before: String
    $first: Int
    $last: Int
  ) {
    saleCataloguesRemove(id: $id, input: $input) {
      errors {
        field
        message
      }
      sale {
        ...SaleDetailsFragment
      }
    }
  }
`;
export const TypedSaleCataloguesRemove = TypedMutation<
  SaleCataloguesRemove,
  SaleCataloguesRemoveVariables
>(saleCataloguesRemove);

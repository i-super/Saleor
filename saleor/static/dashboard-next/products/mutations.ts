import gql from "graphql-tag";
import { Mutation, MutationProps } from "react-apollo";

import {
  ProductCreateMutation,
  ProductCreateMutationVariables,
  ProductDeleteMutation,
  ProductDeleteMutationVariables,
  ProductImageCreateMutation,
  ProductImageCreateMutationVariables,
  ProductImageDeleteMutation,
  ProductImageDeleteMutationVariables,
  ProductImageReorderMutation,
  ProductImageReorderMutationVariables,
  ProductImageUpdateMutation,
  ProductImageUpdateMutationVariables,
  ProductUpdateMutation,
  ProductUpdateMutationVariables,
  VariantCreateMutation,
  VariantCreateMutationVariables,
  VariantDeleteMutation,
  VariantDeleteMutationVariables,
  VariantImageAssignMutation,
  VariantImageAssignMutationVariables,
  VariantImageUnassignMutation,
  VariantImageUnassignMutationVariables,
  VariantUpdateMutation,
  VariantUpdateMutationVariables
} from "../gql-types";

import {
  fragmentProduct,
  fragmentProductImage,
  fragmentVariant
} from "./queries";

export const TypedProductImageCreateMutation = Mutation as React.ComponentType<
  MutationProps<ProductImageCreateMutation, ProductImageCreateMutationVariables>
>;

export const productImageCreateMutation = gql`
  mutation ProductImageCreate($product: ID!, $image: Upload!, $alt: String) {
    productImageCreate(input: { alt: $alt, image: $image, product: $product }) {
      errors {
        field
        message
      }
      productImage {
        id
        sortOrder
        alt
        url
      }
    }
  }
`;

export const TypedProductDeleteMutation = Mutation as React.ComponentType<
  MutationProps<ProductDeleteMutation, ProductDeleteMutationVariables>
>;

export const productDeleteMutation = gql`
  mutation ProductDelete($id: ID!) {
    productDelete(id: $id) {
      errors {
        field
        message
      }
      product {
        id
      }
    }
  }
`;

export const TypedProductImagesReorder = Mutation as React.ComponentType<
  MutationProps<
    ProductImageReorderMutation,
    ProductImageReorderMutationVariables
  >
>;

export const productImagesReorder = gql`
  ${fragmentProductImage}
  mutation ProductImageReorder($productId: ID!, $imagesIds: [ID]!) {
    productImageReorder(productId: $productId, imagesIds: $imagesIds) {
      errors {
        field
        message
      }
      productImages {
        ...ProductImage
      }
    }
  }
`;

export const TypedProductUpdateMutation = Mutation as React.ComponentType<
  MutationProps<ProductUpdateMutation, ProductUpdateMutationVariables>
>;

export const productUpdateMutation = gql`
  ${fragmentProduct}
  mutation ProductUpdate(
    $id: ID!
    $attributes: [AttributeValueInput]
    $availableOn: Date
    $category: ID
    $chargeTaxes: Boolean!
    $collections: [ID]
    $description: String
    $isPublished: Boolean!
    $name: String
    $price: Decimal
  ) {
    productUpdate(
      id: $id
      input: {
        attributes: $attributes
        availableOn: $availableOn
        category: $category
        chargeTaxes: $chargeTaxes
        collections: $collections
        description: $description
        isPublished: $isPublished
        name: $name
        price: $price
      }
    ) {
      errors {
        field
        message
      }
      product {
        ...Product
      }
    }
  }
`;

export const TypedProductCreateMutation = Mutation as React.ComponentType<
  MutationProps<ProductCreateMutation, ProductCreateMutationVariables>
>;

export const productCreateMutation = gql`
  ${fragmentProduct}
  mutation ProductCreate(
    $attributes: [AttributeValueInput]
    $availableOn: Date
    $category: ID!
    $chargeTaxes: Boolean!
    $collections: [ID]
    $description: String
    $isPublished: Boolean!
    $name: String!
    $price: Decimal
    $productType: ID!
  ) {
    productCreate(
      input: {
        attributes: $attributes
        availableOn: $availableOn
        category: $category
        chargeTaxes: $chargeTaxes
        collections: $collections
        description: $description
        isPublished: $isPublished
        name: $name
        price: $price
        productType: $productType
      }
    ) {
      errors {
        field
        message
      }
      product {
        ...Product
      }
    }
  }
`;

export const TypedVariantDeleteMutation = Mutation as React.ComponentType<
  MutationProps<VariantDeleteMutation, VariantDeleteMutationVariables>
>;

export const variantDeleteMutation = gql`
  mutation VariantDelete($id: ID!) {
    productVariantDelete(id: $id) {
      errors {
        field
        message
      }
      productVariant {
        id
      }
    }
  }
`;

export const TypedVariantUpdateMutation = Mutation as React.ComponentType<
  MutationProps<VariantUpdateMutation, VariantUpdateMutationVariables>
>;

export const variantUpdateMutation = gql`
  ${fragmentVariant}
  mutation VariantUpdate(
    $id: ID!
    $attributes: [AttributeValueInput]
    $costPrice: Decimal
    $priceOverride: Decimal
    $product: ID
    $sku: String
    $quantity: Int
    $trackInventory: Boolean!
  ) {
    productVariantUpdate(
      id: $id
      input: {
        attributes: $attributes
        costPrice: $costPrice
        priceOverride: $priceOverride
        product: $product
        sku: $sku
        quantity: $quantity
        trackInventory: $trackInventory
      }
    ) {
      errors {
        field
        message
      }
      productVariant {
        ...ProductVariant
      }
    }
  }
`;

export const TypedVariantCreateMutation = Mutation as React.ComponentType<
  MutationProps<VariantCreateMutation, VariantCreateMutationVariables>
>;

export const variantCreateMutation = gql`
  ${fragmentVariant}
  mutation VariantCreate(
    $attributes: [AttributeValueInput]
    $costPrice: Decimal
    $priceOverride: Decimal
    $product: ID
    $sku: String
    $quantity: Int
    $trackInventory: Boolean!
  ) {
    productVariantCreate(
      input: {
        attributes: $attributes
        costPrice: $costPrice
        priceOverride: $priceOverride
        product: $product
        sku: $sku
        quantity: $quantity
        trackInventory: $trackInventory
      }
    ) {
      errors {
        field
        message
      }
      productVariant {
        ...ProductVariant
      }
    }
  }
`;

export const TypedProductImageDeleteMutation = Mutation as React.ComponentType<
  MutationProps<ProductImageDeleteMutation, ProductImageDeleteMutationVariables>
>;

export const productImageDeleteMutation = gql`
  mutation ProductImageDelete($id: ID!) {
    productImageDelete(id: $id) {
      productImage {
        id
      }
    }
  }
`;

export const TypedProductImageUpdateMutation = Mutation as React.ComponentType<
  MutationProps<ProductImageUpdateMutation, ProductImageUpdateMutationVariables>
>;

export const productImageUpdateMutation = gql`
  mutation ProductImageUpdate($id: ID!, $alt: String!) {
    productImageUpdate(id: $id, input: { alt: $alt }) {
      errors {
        field
        message
      }
      productImage {
        id
        alt
      }
    }
  }
`;

export const TypedVariantImageAssign = Mutation as React.ComponentType<
  MutationProps<VariantImageAssignMutation, VariantImageAssignMutationVariables>
>;

export const variantImageAssignMutation = gql`
  mutation VariantImageAssign($variantId: ID!, $imageId: ID!) {
    variantImageAssign(variantId: $variantId, imageId: $imageId) {
      errors {
        field
        message
      }
      image {
        id
      }
    }
  }
`;

export const TypedVariantImageUnassign = Mutation as React.ComponentType<
  MutationProps<
    VariantImageUnassignMutation,
    VariantImageAssignMutationVariables
  >
>;

export const variantImageUnassignMutation = gql`
  mutation VariantImageUnassign($variantId: ID!, $imageId: ID!) {
    variantImageUnassign(variantId: $variantId, imageId: $imageId) {
      errors {
        field
        message
      }
      image {
        id
      }
    }
  }
`;

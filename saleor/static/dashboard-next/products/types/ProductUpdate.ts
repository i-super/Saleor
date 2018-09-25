/* tslint:disable */
// This file was automatically generated and should not be edited.

import { AttributeValueInput } from "./../../types/globalTypes";

// ====================================================
// GraphQL mutation operation: ProductUpdate
// ====================================================

export interface ProductUpdate_productUpdate_errors {
  __typename: "Error";
  field: string | null;
  message: string | null;
}

export interface ProductUpdate_productUpdate_product_category {
  __typename: "Category";
  id: string;
  name: string;
}

export interface ProductUpdate_productUpdate_product_collections_edges_node {
  __typename: "Collection";
  id: string;
  name: string;
}

export interface ProductUpdate_productUpdate_product_collections_edges {
  __typename: "CollectionCountableEdge";
  node: ProductUpdate_productUpdate_product_collections_edges_node;
}

export interface ProductUpdate_productUpdate_product_collections {
  __typename: "CollectionCountableConnection";
  edges: ProductUpdate_productUpdate_product_collections_edges[];
}

export interface ProductUpdate_productUpdate_product_price {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface ProductUpdate_productUpdate_product_margin {
  __typename: "Margin";
  start: number | null;
  stop: number | null;
}

export interface ProductUpdate_productUpdate_product_purchaseCost_start {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface ProductUpdate_productUpdate_product_purchaseCost_stop {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface ProductUpdate_productUpdate_product_purchaseCost {
  __typename: "MoneyRange";
  start: ProductUpdate_productUpdate_product_purchaseCost_start | null;
  stop: ProductUpdate_productUpdate_product_purchaseCost_stop | null;
}

export interface ProductUpdate_productUpdate_product_attributes_attribute_values {
  __typename: "AttributeValue";
  name: string | null;
  slug: string | null;
}

export interface ProductUpdate_productUpdate_product_attributes_attribute {
  __typename: "Attribute";
  id: string;
  slug: string | null;
  name: string | null;
  values: (ProductUpdate_productUpdate_product_attributes_attribute_values | null)[] | null;
}

export interface ProductUpdate_productUpdate_product_attributes_value {
  __typename: "AttributeValue";
  id: string;
  name: string | null;
  slug: string | null;
}

export interface ProductUpdate_productUpdate_product_attributes {
  __typename: "SelectedAttribute";
  attribute: ProductUpdate_productUpdate_product_attributes_attribute | null;
  value: ProductUpdate_productUpdate_product_attributes_value | null;
}

export interface ProductUpdate_productUpdate_product_availability_priceRange_start_net {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface ProductUpdate_productUpdate_product_availability_priceRange_start {
  __typename: "TaxedMoney";
  net: ProductUpdate_productUpdate_product_availability_priceRange_start_net;
}

export interface ProductUpdate_productUpdate_product_availability_priceRange_stop_net {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface ProductUpdate_productUpdate_product_availability_priceRange_stop {
  __typename: "TaxedMoney";
  net: ProductUpdate_productUpdate_product_availability_priceRange_stop_net;
}

export interface ProductUpdate_productUpdate_product_availability_priceRange {
  __typename: "TaxedMoneyRange";
  start: ProductUpdate_productUpdate_product_availability_priceRange_start | null;
  stop: ProductUpdate_productUpdate_product_availability_priceRange_stop | null;
}

export interface ProductUpdate_productUpdate_product_availability {
  __typename: "ProductAvailability";
  available: boolean | null;
  priceRange: ProductUpdate_productUpdate_product_availability_priceRange | null;
}

export interface ProductUpdate_productUpdate_product_images_edges_node {
  __typename: "ProductImage";
  id: string;
  alt: string;
  sortOrder: number;
  url: string;
}

export interface ProductUpdate_productUpdate_product_images_edges {
  __typename: "ProductImageCountableEdge";
  node: ProductUpdate_productUpdate_product_images_edges_node;
}

export interface ProductUpdate_productUpdate_product_images {
  __typename: "ProductImageCountableConnection";
  edges: ProductUpdate_productUpdate_product_images_edges[];
}

export interface ProductUpdate_productUpdate_product_variants_edges_node_priceOverride {
  __typename: "Money";
  amount: number;
  currency: string;
}

export interface ProductUpdate_productUpdate_product_variants_edges_node {
  __typename: "ProductVariant";
  id: string;
  sku: string;
  name: string;
  priceOverride: ProductUpdate_productUpdate_product_variants_edges_node_priceOverride | null;
  stockQuantity: number;
  margin: number | null;
}

export interface ProductUpdate_productUpdate_product_variants_edges {
  __typename: "ProductVariantCountableEdge";
  node: ProductUpdate_productUpdate_product_variants_edges_node;
}

export interface ProductUpdate_productUpdate_product_variants {
  __typename: "ProductVariantCountableConnection";
  edges: ProductUpdate_productUpdate_product_variants_edges[];
}

export interface ProductUpdate_productUpdate_product_productType {
  __typename: "ProductType";
  id: string;
  name: string;
  hasVariants: boolean;
}

export interface ProductUpdate_productUpdate_product {
  __typename: "Product";
  id: string;
  name: string;
  description: string;
  seoTitle: string | null;
  seoDescription: string | null;
  category: ProductUpdate_productUpdate_product_category;
  collections: ProductUpdate_productUpdate_product_collections | null;
  price: ProductUpdate_productUpdate_product_price | null;
  margin: ProductUpdate_productUpdate_product_margin | null;
  purchaseCost: ProductUpdate_productUpdate_product_purchaseCost | null;
  isPublished: boolean;
  chargeTaxes: boolean;
  availableOn: any | null;
  attributes: (ProductUpdate_productUpdate_product_attributes | null)[] | null;
  availability: ProductUpdate_productUpdate_product_availability | null;
  images: ProductUpdate_productUpdate_product_images | null;
  variants: ProductUpdate_productUpdate_product_variants | null;
  productType: ProductUpdate_productUpdate_product_productType;
  url: string;
}

export interface ProductUpdate_productUpdate {
  __typename: "ProductUpdate";
  errors: (ProductUpdate_productUpdate_errors | null)[] | null;
  product: ProductUpdate_productUpdate_product | null;
}

export interface ProductUpdate {
  productUpdate: ProductUpdate_productUpdate | null;
}

export interface ProductUpdateVariables {
  id: string;
  attributes?: (AttributeValueInput | null)[] | null;
  availableOn?: any | null;
  category?: string | null;
  chargeTaxes: boolean;
  collections?: (string | null)[] | null;
  description?: string | null;
  isPublished: boolean;
  name?: string | null;
  price?: any | null;
}

import { RawDraftContentState } from "draft-js";

import { SingleAutocompleteChoiceType } from "@saleor/components/SingleAutocompleteSelectField";
import { maybe } from "@saleor/misc";
import {
  ProductDetails_product,
  ProductDetails_product_collections,
  ProductDetails_product_variants
} from "@saleor/products/types/ProductDetails";
import { ProductAttributeInput } from "../components/ProductAttributes";
import { ProductCreateData_productTypes_edges_node_productAttributes } from "../types/ProductCreateData";

export interface Collection {
  id: string;
  label: string;
}

interface Node {
  id: string;
  name: string;
}

export interface ProductType {
  hasVariants: boolean;
  id: string;
  name: string;
  productAttributes: ProductCreateData_productTypes_edges_node_productAttributes[];
}

// TODO: Take attributes from product type
export function getAttributeInputFromProduct(
  product: ProductDetails_product
): ProductAttributeInput[] {
  return maybe(
    (): ProductAttributeInput[] =>
      product.attributes.map(attribute => ({
        data: {
          inputType: attribute.attribute.inputType,
          values: attribute.attribute.values
        },
        id: attribute.attribute.id,
        label: attribute.attribute.name,
        value: attribute.value.slug
      })),
    []
  );
}

export function getAttributeInputFromProductType(
  productType: ProductType
): ProductAttributeInput[] {
  return productType.productAttributes.map(attribute => ({
    data: {
      inputType: attribute.inputType,
      values: attribute.values
    },
    id: attribute.id,
    label: attribute.name,
    value: ""
  }));
}

export function getCollectionInput(
  productCollections: ProductDetails_product_collections[]
): Collection[] {
  return maybe(
    () =>
      productCollections.map(collection => ({
        id: collection.id,
        label: collection.name
      })),
    []
  );
}

export function getChoices(nodes: Node[]): SingleAutocompleteChoiceType[] {
  return maybe(
    () =>
      nodes.map(node => ({
        label: node.name,
        value: node.id
      })),
    []
  );
}

export interface ProductUpdatePageFormData {
  basePrice: number;
  category: string | null;
  chargeTaxes: boolean;
  description: RawDraftContentState;
  isPublished: boolean;
  name: string;
  publicationDate: string;
  seoDescription: string;
  seoTitle: string;
  sku: string;
  stockQuantity: number;
}

export function getProductUpdatePageFormData(
  product: ProductDetails_product,
  variants: ProductDetails_product_variants[]
): ProductUpdatePageFormData {
  return {
    basePrice: maybe(() => product.basePrice.amount),
    category: maybe(() => product.category.id),
    chargeTaxes: maybe(() => product.chargeTaxes, false),
    description: maybe(() => JSON.parse(product.descriptionJson)),
    isPublished: maybe(() => product.isPublished, false),
    name: maybe(() => product.name),
    publicationDate: maybe(() => product.publicationDate),
    seoDescription: maybe(() => product.seoDescription) || "",
    seoTitle: maybe(() => product.seoTitle) || "",
    sku: maybe(() =>
      product.productType.hasVariants
        ? undefined
        : variants && variants[0]
        ? variants[0].sku
        : undefined
    ),
    stockQuantity: maybe(() =>
      product.productType.hasVariants
        ? undefined
        : variants && variants[0]
        ? variants[0].quantity
        : undefined
    )
  };
}

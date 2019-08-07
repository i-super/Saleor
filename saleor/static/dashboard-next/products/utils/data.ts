import { RawDraftContentState } from "draft-js";

import { MultiAutocompleteChoiceType } from "@saleor/components/MultiAutocompleteSelectField";
import { SingleAutocompleteChoiceType } from "@saleor/components/SingleAutocompleteSelectField";
import { maybe } from "@saleor/misc";
import {
  ProductDetails_product,
  ProductDetails_product_collections,
  ProductDetails_product_variants
} from "@saleor/products/types/ProductDetails";
import { UserError } from "@saleor/types";
import { ProductAttributeInput } from "../components/ProductAttributes";
import { VariantAttributeInput } from "../components/ProductVariantAttributes";
import { ProductCreateData_productTypes_edges_node_productAttributes } from "../types/ProductCreateData";
import {
  ProductVariant,
  ProductVariant_attributes_attribute
} from "../types/ProductVariant";
import {
  ProductVariantCreateData_product,
  ProductVariantCreateData_product_productType_variantAttributes
} from "../types/ProductVariantCreateData";

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

export function getAttributeInputFromProduct(
  product: ProductDetails_product
): ProductAttributeInput[] {
  return maybe(
    (): ProductAttributeInput[] =>
      product.attributes.map(attribute => ({
        data: {
          inputType: attribute.attribute.inputType,
          isRequired: attribute.attribute.valueRequired,
          values: attribute.attribute.values
        },
        id: attribute.attribute.id,
        label: attribute.attribute.name,
        value: attribute.values.map(value => value.slug)
      })),
    []
  );
}

export interface ProductAttributeValueChoices {
  id: string;
  values: MultiAutocompleteChoiceType[];
}
export function getSelectedAttributesFromProduct(
  product: ProductDetails_product
): ProductAttributeValueChoices[] {
  return maybe(
    () =>
      product.attributes.map(attribute => ({
        id: attribute.attribute.id,
        values: attribute.values.map(value => ({
          label: value.name,
          value: value.slug
        }))
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
      isRequired: attribute.valueRequired,
      values: attribute.values
    },
    id: attribute.id,
    label: attribute.name,
    value: []
  }));
}

export function getAttributeInputFromVariant(
  product: ProductVariant
): VariantAttributeInput[] {
  return maybe(
    (): VariantAttributeInput[] =>
      product.attributes.map(attribute => ({
        data: {
          values: attribute.attribute.values
        },
        id: attribute.attribute.id,
        label: attribute.attribute.name,
        value: attribute.value.slug
      })),
    []
  );
}

export function getVariantAttributeInputFromProduct(
  product: ProductVariantCreateData_product
): VariantAttributeInput[] {
  return maybe(() =>
    product.productType.variantAttributes.map(attribute => ({
      data: {
        values: attribute.values
      },
      id: attribute.id,
      label: attribute.name,
      value: ""
    }))
  );
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
  collections: string[];
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
    basePrice: maybe(() => product.basePrice.amount, 0),
    category: maybe(() => product.category.id, ""),
    chargeTaxes: maybe(() => product.chargeTaxes, false),
    collections: maybe(
      () => product.collections.map(collection => collection.id),
      []
    ),
    description: maybe(() => JSON.parse(product.descriptionJson)),
    isPublished: maybe(() => product.isPublished, false),
    name: maybe(() => product.name, ""),
    publicationDate: maybe(() => product.publicationDate, ""),
    seoDescription: maybe(() => product.seoDescription, ""),
    seoTitle: maybe(() => product.seoTitle, ""),
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

export function getVariantAttributeErrors(
  errors: UserError[],
  variantAttributes: Array<
    | ProductVariantCreateData_product_productType_variantAttributes
    | ProductVariant_attributes_attribute
  >
): Record<string, string> {
  return maybe(
    () =>
      errors.reduce((acc, err) => {
        const slug = err.field.split(":")[1];
        const attribute = variantAttributes.find(
          attribute => attribute.slug === slug
        );

        if (!!attribute) {
          acc[attribute.id] = err.message;
        }

        return acc;
      }, {}),
    {}
  );
}

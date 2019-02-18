import * as React from "react";

import CardSpacer from "../../../components/CardSpacer";
import { ConfirmButtonTransitionState } from "../../../components/ConfirmButton/ConfirmButton";
import Container from "../../../components/Container";
import Form from "../../../components/Form";
import Grid from "../../../components/Grid";
import PageHeader from "../../../components/PageHeader";
import SaveButtonBar from "../../../components/SaveButtonBar/SaveButtonBar";
import SeoForm from "../../../components/SeoForm";
import i18n from "../../../i18n";
import { UserError } from "../../../types";
import {
  ProductDetails_product,
  ProductDetails_product_attributes_attribute,
  ProductDetails_product_images,
  ProductDetails_product_variants
} from "../../types/ProductDetails";
import ProductAvailabilityForm from "../ProductAvailabilityForm";
import ProductDetailsForm from "../ProductDetailsForm";
import ProductImages from "../ProductImages";
import ProductOrganization from "../ProductOrganization";
import ProductPricing from "../ProductPricing";
import ProductStock from "../ProductStock";
import ProductVariants from "../ProductVariants";

interface ProductUpdateProps {
  errors: UserError[];
  placeholderImage: string;
  collections?: Array<{
    id: string;
    name: string;
  }>;
  categories?: Array<{
    id: string;
    name: string;
  }>;
  disabled?: boolean;
  productCollections?: Array<{
    id: string;
    name: string;
  }>;
  variants: ProductDetails_product_variants[];
  images?: ProductDetails_product_images[];
  product?: ProductDetails_product;
  header: string;
  saveButtonBarState: ConfirmButtonTransitionState;
  fetchCategories: (query: string) => void;
  fetchCollections: (query: string) => void;
  onVariantShow: (id: string) => () => void;
  onImageDelete: (id: string) => () => void;
  onAttributesEdit: () => void;
  onBack?();
  onDelete();
  onImageEdit?(id: string);
  onImageReorder?(event: { oldIndex: number; newIndex: number });
  onImageUpload(file: File);
  onProductShow?();
  onSeoClick?();
  onSubmit?(data: any);
  onVariantAdd?();
}

interface ChoiceType {
  label: string;
  value: string;
}
export interface FormData {
  attributes: Array<{
    slug: string;
    value: string;
  }>;
  available: boolean;
  category: ChoiceType | null;
  chargeTaxes: boolean;
  collections: ChoiceType[];
  description: string;
  name: string;
  price: string;
  productType: {
    label: string;
    value: {
      hasVariants: boolean;
      id: string;
      name: string;
      productAttributes: Array<
        Exclude<ProductDetails_product_attributes_attribute, "__typename">
      >;
    };
  } | null;
  publicationDate: string;
  seoDescription: string;
  seoTitle: string;
  sku: string;
  stockQuantity: number;
}

export const ProductUpdate: React.StatelessComponent<ProductUpdateProps> = ({
  disabled,
  categories: categoryChoiceList,
  collections: collectionChoiceList,
  errors: userErrors,
  fetchCategories,
  fetchCollections,
  images,
  header,
  placeholderImage,
  product,
  productCollections,
  saveButtonBarState,
  variants,
  onAttributesEdit,
  onBack,
  onDelete,
  onImageDelete,
  onImageEdit,
  onImageReorder,
  onImageUpload,
  onSeoClick,
  onSubmit,
  onVariantAdd,
  onVariantShow
}) => {
  const initialData: FormData = product
    ? {
        attributes: product.attributes
          ? product.attributes.map(a => ({
              slug: a.attribute.slug,
              value: a.value ? a.value.slug : null
            }))
          : undefined,
        available: product.isPublished,
        category: product.category
          ? {
              label: product.category.name,
              value: product.category.id
            }
          : undefined,
        chargeTaxes: product.chargeTaxes ? product.chargeTaxes : false,
        collections: productCollections
          ? productCollections.map(collection => ({
              label: collection.name,
              value: collection.id
            }))
          : [],
        description: product.description,
        name: product.name,
        price: product.price ? product.price.amount.toString() : undefined,
        productType:
          product.productType && product.attributes
            ? {
                label: product.productType.name,
                value: {
                  hasVariants: product.productType.hasVariants,
                  id: product.productType.id,
                  name: product.productType.name,
                  productAttributes: product.attributes.map(a => a.attribute)
                }
              }
            : undefined,
        publicationDate: product.publicationDate,
        seoDescription: product.seoDescription,
        seoTitle: product.seoTitle,
        sku:
          product.productType && product.productType.hasVariants
            ? undefined
            : variants && variants[0]
            ? variants[0].sku
            : undefined,
        stockQuantity:
          product.productType && product.productType.hasVariants
            ? undefined
            : variants && variants[0]
            ? variants[0].quantity
            : undefined
      }
    : {
        attributes: [],
        available: false,
        category: null,
        chargeTaxes: false,
        collections: [],
        description: "",
        name: "",
        price: "",
        productType: null,
        publicationDate: "",
        seoDescription: "",
        seoTitle: "",
        sku: "",
        stockQuantity: 0
      };
  const categories =
    categoryChoiceList !== undefined
      ? categoryChoiceList.map(category => ({
          label: category.name,
          value: category.id
        }))
      : [];
  const collections =
    collectionChoiceList !== undefined
      ? collectionChoiceList.map(collection => ({
          label: collection.name,
          value: collection.id
        }))
      : [];
  const currency =
    product && product.price ? product.price.currency : undefined;
  const hasVariants =
    product && product.productType && product.productType.hasVariants;

  return (
    <Form
      onSubmit={onSubmit}
      errors={userErrors}
      initial={initialData}
      confirmLeave
    >
      {({ change, data, errors, hasChanged, submit }) => (
        <>
          <Container width="md">
            <PageHeader title={header} onBack={onBack} />
            <Grid>
              <div>
                <ProductDetailsForm
                  data={data}
                  disabled={disabled}
                  errors={errors}
                  onChange={change}
                />
                <CardSpacer />
                <ProductImages
                  images={images}
                  placeholderImage={placeholderImage}
                  onImageDelete={onImageDelete}
                  onImageReorder={onImageReorder}
                  onImageEdit={onImageEdit}
                  onImageUpload={onImageUpload}
                />
                <CardSpacer />
                <ProductPricing
                  currency={currency}
                  data={data}
                  disabled={disabled}
                  onChange={change}
                />
                <CardSpacer />
                {hasVariants ? (
                  <ProductVariants
                    variants={variants}
                    fallbackPrice={product ? product.price : undefined}
                    onAttributesEdit={onAttributesEdit}
                    onRowClick={onVariantShow}
                    onVariantAdd={onVariantAdd}
                  />
                ) : (
                  <ProductStock
                    data={data}
                    disabled={disabled}
                    product={product}
                    onChange={change}
                  />
                )}
                <CardSpacer />
                <SeoForm
                  helperText={i18n.t(
                    "Add search engine title and description to make this product easier to find"
                  )}
                  title={data.seoTitle}
                  titlePlaceholder={data.name}
                  description={data.seoDescription}
                  descriptionPlaceholder={data.description}
                  loading={disabled}
                  onClick={onSeoClick}
                  onChange={change}
                />
              </div>
              <div>
                <ProductOrganization
                  categories={categories}
                  errors={errors}
                  fetchCategories={fetchCategories}
                  fetchCollections={fetchCollections}
                  collections={collections}
                  product={product}
                  data={data}
                  disabled={disabled}
                  onChange={change}
                />
                <CardSpacer />
                <ProductAvailabilityForm
                  data={data}
                  errors={errors}
                  loading={disabled}
                  onChange={change}
                />
              </div>
            </Grid>
            <SaveButtonBar
              onCancel={onBack}
              onDelete={onDelete}
              onSave={submit}
              state={saveButtonBarState}
              disabled={disabled || !hasChanged}
            />
          </Container>
        </>
      )}
    </Form>
  );
};
ProductUpdate.displayName = "ProductUpdate";
export default ProductUpdate;

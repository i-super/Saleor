import Hidden from "material-ui/Hidden";
import { withStyles } from "material-ui/styles";
import * as React from "react";

import { productEditUrl, productImageEditUrl, productShowUrl } from "..";
import { productStorefrontUrl } from "../";
import ErrorMessageCard from "../../components/ErrorMessageCard";
import Navigator from "../../components/Navigator";
import ProductCollections from "../components/ProductCollections";
import ProductDescription from "../components/ProductDescription";
import ProductDetailsPage from "../components/ProductDetailsPage";
import ProductImages from "../components/ProductImages";
import ProductPriceAndAvailability from "../components/ProductPriceAndAvailability";
import ProductVariants from "../components/ProductVariants";
import {
  productImageCreateMutation,
  TypedProductImageCreateMutation
} from "../mutations";
import { productDetailsQuery, TypedProductDetailsQuery } from "../queries";

interface ProductDetailsProps {
  id: string;
}

const decorate = withStyles(theme => ({
  root: {
    display: "grid",
    gridGap: theme.spacing.unit + "px",
    gridTemplateColumns: "100%",
    [theme.breakpoints.up("md")]: {
      gridGap: theme.spacing.unit * 2 + "px",
      gridTemplateColumns: "3fr 1fr"
    }
  }
}));

export const ProductDetails = decorate<ProductDetailsProps>(
  ({ classes, id }) => (
    <Navigator>
      {navigate => (
        <TypedProductDetailsQuery
          query={productDetailsQuery}
          variables={{ id }}
        >
          {({ data, error, loading }) => {
            if (error) {
              return <ErrorMessageCard message={error.message} />;
            }
            return (
              <TypedProductImageCreateMutation
                mutation={productImageCreateMutation}
              >
                {(uploadImage, { data: imageUploadData, error }) => {
                  if (error) {
                    return <ErrorMessageCard message={error.message} />;
                  }

                  const handleImageUpload = (event: React.ChangeEvent<any>) => {
                    uploadImage({
                      variables: { id, file: event.target.files[0] }
                    });
                  };
                  return (
                    <ProductDetailsPage
                      onBack={() => window.history.back()}
                      onCollectionShow={() => () => navigate("#")}
                      onDelete={() => {}}
                      onEdit={id => () => navigate(productEditUrl(id))}
                      onImageEdit={id => () =>
                        navigate(productImageEditUrl(id))}
                      onImageUpload={handleImageUpload}
                      onImageReorder={() => {}}
                      onProductPublish={() => {}}
                      onProductShow={id => () => navigate(productShowUrl(id))}
                      onVariantShow={() => {}}
                      // TODO: replace with something nicers
                      placeholderImage={"/static/images/placeholder255x255.png"}
                      product={data && data.product ? data.product : undefined}
                    />
                  );
                }}
              </TypedProductImageCreateMutation>
            );
          }}
        </TypedProductDetailsQuery>
      )}
    </Navigator>
  )
);
export default ProductDetails;

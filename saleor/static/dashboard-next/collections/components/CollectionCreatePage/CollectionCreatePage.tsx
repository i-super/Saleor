import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import { withStyles } from "@material-ui/core/styles";
import * as React from "react";

import { CardSpacer } from "../../../components/CardSpacer";
import CardTitle from "../../../components/CardTitle";
import { Container } from "../../../components/Container";
import { ControlledSwitch } from "../../../components/ControlledSwitch";
import Form from "../../../components/Form";
import PageHeader from "../../../components/PageHeader";
import SaveButtonBar from "../../../components/SaveButtonBar";
import SeoForm from "../../../components/SeoForm";
import i18n from "../../../i18n";
import { UserError } from "../../../types";
import CollectionDetails from "../CollectionDetails/CollectionDetails";
import { CollectionImage } from "../CollectionImage/CollectionImage";

export interface CollectionCreatePageFormData {
  backgroundImage: {
    url: string;
    value: string;
  };
  name: string;
  isPublished: boolean;
  seoDescription: string;
  seoTitle: string;
}

export interface CollectionCreatePageProps {
  disabled: boolean;
  errors: UserError[];
  onBack: () => void;
  onSubmit: (data: CollectionCreatePageFormData) => void;
}

const initialForm: CollectionCreatePageFormData = {
  backgroundImage: {
    url: null,
    value: null
  },
  isPublished: false,
  name: "",
  seoDescription: "",
  seoTitle: ""
};

const decorate = withStyles(theme => ({
  root: {
    display: "grid" as "grid",
    gridColumnGap: theme.spacing.unit * 2 + "px",
    gridTemplateColumns: "9fr 4fr"
  }
}));
const CollectionCreatePage = decorate<CollectionCreatePageProps>(
  ({ classes, disabled, errors, onBack, onSubmit }) => (
    <Form errors={errors} initial={initialForm} onSubmit={onSubmit}>
      {({ change, data, errors: formErrors, hasChanged, submit }) => (
        <Container width="md">
          <PageHeader
            title={i18n.t("Add collection", {
              context: "page title"
            })}
            onBack={onBack}
          />
          <div className={classes.root}>
            <div>
              <CollectionDetails
                data={data}
                disabled={disabled}
                errors={formErrors}
                onChange={change}
              />
              <CardSpacer />
              <CollectionImage
                image={
                  data.backgroundImage.url
                    ? { __typename: "Image", url: data.backgroundImage.url }
                    : null
                }
                onImageDelete={() =>
                  change({
                    target: {
                      name: "backgroundImage",
                      value: {
                        url: null,
                        value: null
                      }
                    }
                  } as any)
                }
                onImageUpload={event =>
                  change({
                    target: {
                      name: "backgroundImage",
                      value: {
                        url: URL.createObjectURL(event.target.files[0]),
                        value: event.target.files[0]
                      }
                    }
                  } as any)
                }
              />
              <CardSpacer />
              <SeoForm
                description={data.seoDescription}
                disabled={disabled}
                descriptionPlaceholder=""
                helperText={i18n.t(
                  "Add search engine title and description to make this collection easier to find",
                  {
                    context: "help text"
                  }
                )}
                title={data.seoTitle}
                titlePlaceholder={data.name}
                onChange={change}
              />
            </div>
            <div>
              <div>
                <Card>
                  <CardTitle
                    title={i18n.t("Availability", {
                      context: "collection status"
                    })}
                  />
                  <CardContent>
                    <ControlledSwitch
                      checked={data.isPublished}
                      disabled={disabled}
                      name="isPublished"
                      onChange={change}
                      label={i18n.t("Publish on storefront", {
                        context: "button"
                      })}
                    />
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
          <SaveButtonBar
            disabled={disabled || !hasChanged}
            onCancel={onBack}
            onSave={submit}
          />
        </Container>
      )}
    </Form>
  )
);
CollectionCreatePage.displayName = "CollectionCreatePage";
export default CollectionCreatePage;

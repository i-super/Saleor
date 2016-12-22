import _ from 'lodash';
import $ from 'jquery';
import classNames from 'classnames';
import React, { Component, PropTypes } from 'react';

import AttributeSelectionWidget from './AttributeSelectionWidget';
import QuantityInput from './QuantityInput';


export default class VariantPicker extends Component {

  static propTypes = {
    attributes: PropTypes.array.isRequired,
    url: PropTypes.string.isRequired,
    variants: PropTypes.array.isRequired
  }

  constructor(props) {
    super(props);
    this.state = {
      errors: {},
      quantity: 1,
      selection: {},
      variant: null
    };
  }

  handleAddToCart = () => {
    const { quantity, variant } = this.state;
    if (quantity > 0 && variant) {
      $.ajax({
        url: this.props.url,
        method: 'post',
        data: {
          quantity: quantity,
          variant: variant.id
        },
        success: (response) => {
          const { next } = response;
          if (next) {
            window.location = next;
          } else {
            location.reload();
          }
        },
        error: (response) => {
          const { error } = response.responseJSON;
          if (error) {
            this.setState({ errors: response.responseJSON.error });
          }
        }
      });
    }
  }

  handleAttributeChange = (attrId, valueId) => {
    this.setState({
      selection: Object.assign(this.state.selection, { [attrId]: valueId })
    }, () => {
      let matchedVariant = null;
      this.props.variants.forEach(variant => {
        if (_.isEqual(this.state.selection, variant.attributes)) {
          matchedVariant = variant;
        }
      });
      this.setState({variant: matchedVariant});
    });
  }

  handleQuantityChange = (event) => {
    this.setState({quantity: parseInt(event.target.value)});
  }

  render() {
    const { attributes } = this.props;
    const { quantity, variant, errors } = this.state;

    const addToCartBtnClasses = classNames({
      'btn btn-lg btn-block btn-primary': true,
      'disabled': !variant
    });

    return (
      <div>
        {attributes.map((attribute, i) =>
          <AttributeSelectionWidget
            attribute={attribute}
            handleChange={this.handleAttributeChange}
            key={i}
          />
        )}
        <QuantityInput
          errors={errors.quantity}
          handleChange={this.handleQuantityChange}
          quantity={quantity}
        />
        <div className="form-group">
          <button
            className={addToCartBtnClasses}
            onClick={this.handleAddToCart}>
            Add to cart
          </button>
        </div>
      </div>
    );
  }
}

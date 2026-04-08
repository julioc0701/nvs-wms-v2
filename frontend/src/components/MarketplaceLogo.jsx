import React from 'react';
import mlLogoSrc from '../assets/ml-logo-v3.png'
import shopeeLogoSrc from '../assets/shopee-logo-v3.png'

const MarketplaceLogo = ({ marketplace, size = 24, className = "" }) => {
  if (marketplace === 'ml') {
    return (
      <img
        src={mlLogoSrc}
        alt="Mercado Livre"
        draggable="false"
        style={{ width: 'auto', height: size, objectFit: 'contain', mixBlendMode: 'multiply' }}
        className={`inline-block transition-all duration-500 group-hover:scale-110 drop-shadow-md ${className}`}
      />
    );
  }
  if (marketplace === 'shopee') {
    return (
      <img
        src={shopeeLogoSrc}
        alt="Shopee"
        draggable="false"
        style={{ width: 'auto', height: size, objectFit: 'contain', mixBlendMode: 'multiply' }}
        className={`inline-block transition-all duration-500 group-hover:scale-110 drop-shadow-md ${className}`}
      />
    );
  }
  return null;
};

export default MarketplaceLogo;

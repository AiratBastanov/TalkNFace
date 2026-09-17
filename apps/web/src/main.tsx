import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import { Product } from './product';

const root = document.getElementById('root');
if (!root) throw new Error('Application root is missing');

createRoot(root).render(
  <StrictMode>
    <Product />
  </StrictMode>,
);

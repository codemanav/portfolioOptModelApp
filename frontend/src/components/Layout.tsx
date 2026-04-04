import styles from '../styles/components/Layout.module.css';

// Components
import Navbar from './Navbar';

type LayoutProps = {
    children: JSX.Element | JSX.Element[]
}

const Layout = ({ children }: LayoutProps) => {
  return (
    <>
      <Navbar />
      <div className={`${styles.container} bg-gray-200`}>
        <main className={styles.main}>
          {children}
        </main>
      </div>
    </>
  )
}

export default Layout
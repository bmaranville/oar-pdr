package gov.nist.oar.customizationapi.config.SAMLConfig;

import static org.junit.Assert.assertEquals;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.junit4.SpringJUnit4ClassRunner;
import org.springframework.test.context.web.WebAppConfiguration;
import org.springframework.test.context.support.AnnotationConfigContextLoader;
@RunWith(SpringJUnit4ClassRunner.class)
@ContextConfiguration(classes = {SamlSecurityConfig.class}, loader = AnnotationConfigContextLoader.class)
//@WebAppConfiguration
@TestPropertySource(locations = "classpath:testapp.yml")
public class SamlSecurityConfigTest {

	@Autowired
	SamlSecurityConfig samlSecurityConfig;
	/**
	 * Entityid for the SAML service provider, in this case customization service
	 */
	@Value("${saml.metdata.entityid:testid}")
	String entityId;


	@Test
	public void readConfigsTest() {
		assertEquals(entityId, "gov:nist:oar:localhost");
		assertEquals(samlSecurityConfig.applicationURL, "https://localhost/pdr/about");
		assertEquals(samlSecurityConfig.samlServer, "localhost");
		assertEquals("https://localhost/customization", samlSecurityConfig.entityBaseURL);
		
	}

}
